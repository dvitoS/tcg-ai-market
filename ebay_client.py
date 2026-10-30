"""eBay Browse API — aktivni oglasi (search item summaries)."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.parse import quote

import requests

from config import ENV_PATH, PROJECT_ROOT, get_ebay_credentials

LOG = logging.getLogger("tcg.ebay")

EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"
# Public Browse search scope (application token).
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
# Pokémon TCG Individual Cards (US). Soft filter — search still works without it.
EBAY_POKEMON_CATEGORY_ID = "183454"

_token_cache: dict[str, Any] = {"access_token": "", "expires_at": 0.0}


def ebay_configured() -> bool:
    """True ako imamo App+Cert (client credentials) ili spremljeni OAuth token."""
    app_id, cert_id, _dev, oauth = get_ebay_credentials()
    return bool((app_id and cert_id) or oauth)


def _marketplace_id() -> str:
    from config import _secret

    return (_secret("EBAY_MARKETPLACE_ID") or "EBAY_US").strip() or "EBAY_US"


def _fetch_application_token(app_id: str, cert_id: str) -> tuple[str, float]:
    """Client-credentials OAuth → (access_token, expires_at_epoch)."""
    basic = base64.b64encode(
        f"{quote(app_id, safe='')}:{quote(cert_id, safe='')}".encode("utf-8")
    ).decode("ascii")
    response = requests.post(
        EBAY_OAUTH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": EBAY_SCOPE,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        LOG.warning("eBay OAuth failed %s: %s", response.status_code, response.text[:300])
        response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("eBay OAuth nije vratio access_token.")
    expires_in = float(payload.get("expires_in") or 7200)
    # Refresh malo prije isteka.
    return token, time.time() + max(60.0, expires_in - 120.0)


def get_access_token(*, force_refresh: bool = False) -> str:
    """Preferiraj application token (App+Cert); fallback EBAY_OAUTH_TOKEN."""
    app_id, cert_id, _dev, oauth = get_ebay_credentials()

    if app_id and cert_id:
        now = time.time()
        cached = str(_token_cache.get("access_token") or "")
        expires_at = float(_token_cache.get("expires_at") or 0.0)
        if not force_refresh and cached and now < expires_at:
            return cached
        token, expires_at = _fetch_application_token(app_id, cert_id)
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = expires_at
        return token

    if oauth:
        return oauth

    raise RuntimeError(
        "eBay credentials nisu postavljeni. Dodaj EBAY_APP_ID + EBAY_CERT_ID "
        "(ili EBAY_OAUTH_TOKEN) u .env / Streamlit Secrets."
    )


def _browse_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": _marketplace_id(),
    }


def build_search_query(
    *,
    name: str,
    set_name: str | None = None,
    number: str | None = None,
) -> str:
    parts = ["Pokemon", (name or "").strip()]
    if set_name:
        parts.append(str(set_name).strip())
    if number:
        parts.append(str(number).strip())
    return " ".join(p for p in parts if p)


def normalize_listing(item: dict[str, Any]) -> dict[str, Any]:
    price_obj = item.get("price") or {}
    current = item.get("currentBidPrice") or {}
    value = price_obj.get("value")
    currency = price_obj.get("currency") or "USD"
    if value is None and current.get("value") is not None:
        value = current.get("value")
        currency = current.get("currency") or currency
    try:
        price = float(value) if value is not None else None
    except (TypeError, ValueError):
        price = None
    image = (item.get("image") or {}).get("imageUrl") or ""
    seller = (item.get("seller") or {}).get("username") or ""
    return {
        "item_id": str(item.get("itemId") or ""),
        "title": str(item.get("title") or ""),
        "price": price,
        "currency": str(currency),
        "condition": str(item.get("condition") or ""),
        "url": str(item.get("itemWebUrl") or item.get("itemHref") or ""),
        "image": str(image),
        "seller": str(seller),
        "buying_options": list(item.get("buyingOptions") or []),
    }


def search_item_summaries(
    q: str,
    *,
    limit: int = 8,
    category_id: str | None = EBAY_POKEMON_CATEGORY_ID,
) -> list[dict[str, Any]]:
    """GET /buy/browse/v1/item_summary/search → normalizirani listing dictovi."""
    query = (q or "").strip()
    if not query:
        return []

    token = get_access_token()
    params: dict[str, Any] = {
        "q": query,
        "limit": max(1, min(int(limit), 50)),
    }
    if category_id:
        params["category_ids"] = category_id

    url = f"{EBAY_BROWSE_BASE}/item_summary/search"
    response = requests.get(
        url,
        params=params,
        headers=_browse_headers(token),
        timeout=35,
    )
    # Expired user/app token → jednom refresh pa retry (samo ako imamo App+Cert).
    if response.status_code == 401:
        app_id, cert_id, _, _ = get_ebay_credentials()
        if app_id and cert_id:
            token = get_access_token(force_refresh=True)
            response = requests.get(
                url,
                params=params,
                headers=_browse_headers(token),
                timeout=35,
            )

    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "3")
        wait = float(retry) if str(retry).replace(".", "", 1).isdigit() else 3.0
        LOG.warning("eBay Browse 429 — čekam %.0fs", wait)
        time.sleep(wait)
        response = requests.get(
            url,
            params=params,
            headers=_browse_headers(token),
            timeout=35,
        )

    if response.status_code >= 400:
        LOG.warning("eBay Browse %s: %s", response.status_code, response.text[:400])
        response.raise_for_status()

    payload = response.json() if response.content else {}
    items = payload.get("itemSummaries") or []
    return [normalize_listing(item) for item in items if isinstance(item, dict)]


def listings_for_card(
    *,
    name: str,
    set_name: str | None = None,
    number: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search oglasa za Pokémon kartu (ime + set + broj)."""
    q = build_search_query(name=name, set_name=set_name, number=number)
    rows = search_item_summaries(q, limit=limit)
    if rows or not set_name:
        return rows
    # Soft fallback: samo ime ako set suzi previše.
    return search_item_summaries(
        build_search_query(name=name, set_name=None, number=number),
        limit=limit,
    )


def sold_comps_for_card(
    *,
    name: str,
    set_name: str | None = None,
    number: str | None = None,
    limit: int = 8,
) -> tuple[list[dict[str, Any]], str | None]:
    """Best-effort sold comps via Marketplace Insights (often gated).

    Returns (rows, error_or_hint). When Insights is unavailable, returns ([], hint)
    so the UI can show active Browse listings as a soft fallback caption.
    """
    q = build_search_query(name=name, set_name=set_name, number=number)
    if not q or not ebay_configured():
        return [], "eBay credentials missing."

    token = get_access_token()
    # Marketplace Insights item sales — requires special API access on most apps.
    url = "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"
    params: dict[str, Any] = {
        "q": q,
        "limit": max(1, min(int(limit), 20)),
        "category_ids": EBAY_POKEMON_CATEGORY_ID,
    }
    try:
        response = requests.get(
            url,
            params=params,
            headers=_browse_headers(token),
            timeout=35,
        )
    except requests.RequestException as exc:
        return [], str(exc)[:180]

    if response.status_code in {401, 403, 404}:
        return (
            [],
            "eBay Marketplace Insights is not enabled for this app — showing active listings only.",
        )
    if response.status_code >= 400:
        LOG.warning("eBay Insights %s: %s", response.status_code, response.text[:300])
        return [], f"eBay Insights HTTP {response.status_code}"

    payload = response.json() if response.content else {}
    items = payload.get("itemSales") or payload.get("itemSummaries") or []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        price_obj = item.get("lastSoldPrice") or item.get("price") or {}
        try:
            price = float(price_obj.get("value")) if price_obj.get("value") is not None else None
        except (TypeError, ValueError):
            price = None
        rows.append(
            {
                "item_id": str(item.get("itemId") or ""),
                "title": str(item.get("title") or ""),
                "price": price,
                "currency": str(price_obj.get("currency") or "USD"),
                "condition": str(item.get("condition") or ""),
                "url": str(item.get("itemWebUrl") or item.get("itemHref") or ""),
                "sold_date": str(item.get("soldDate") or item.get("lastSoldDate") or ""),
                "image": str((item.get("image") or {}).get("imageUrl") or ""),
            }
        )
    return rows, None


# Reload dotenv helper for Streamlit hot paths (imported by tests/smoke).
def _reload_env() -> None:
    from dotenv import load_dotenv
    import os

    load_dotenv(ENV_PATH, override=False)
    if not os.environ.get("GITHUB_ACTIONS"):
        load_dotenv(PROJECT_ROOT / "tcg.env.txt", override=False)
