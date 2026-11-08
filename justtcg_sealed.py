"""JustTCG sealed product quotes (ETB / box / tin) via v2 gtin or tcgplayer id."""

from __future__ import annotations

import logging
import re
from typing import Any

LOG = logging.getLogger("tcg.justtcg.sealed")


def _client():
    import justtcg_client as jtcg

    return jtcg


def sealed_card_id(tcgplayer_id: str) -> str:
    tid = re.sub(r"[^0-9A-Za-z_-]", "", str(tcgplayer_id or "").strip())
    return f"sealed:{tid}" if tid else ""


def _external_tcp(card: dict[str, Any]) -> str | None:
    external = card.get("external_ids") if isinstance(card.get("external_ids"), dict) else {}
    for key in ("tcgplayer", "tcgplayerId", "tcgplayer_id"):
        raw = external.get(key) if key in external else card.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _spot_from_card(card: dict[str, Any] | None) -> float | None:
    if not card:
        return None
    variants = list(card.get("variants") or [])
    # Sealed often has a single “Sealed” / “Ungraded” variant.
    jtcg = _client()
    nm = jtcg.pick_nm_variant(variants)
    price = jtcg.variant_price_usd(nm)
    if price is not None:
        return price
    for variant in variants:
        price = jtcg.variant_price_usd(variant)
        if price is not None:
            return price
    # v2 market shape
    for variant in variants:
        markets = variant.get("markets")
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            for key in ("price", "last_price", "lastKnownPrice"):
                try:
                    value = float(market.get(key))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    return value
    try:
        value = float(card.get("price"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def tcgplayer_product_image(tcgplayer_id: str | None) -> str | None:
    """Stable TCGPlayer CDN art when JustTCG omits an image URL."""
    tid = str(tcgplayer_id or "").strip()
    if not re.fullmatch(r"\d{4,12}", tid):
        return None
    return f"https://tcgplayer-cdn.tcgplayer.com/product/{tid}_in_1000x1000.jpg"


def _http_url(raw: Any) -> str | None:
    text = str(raw or "").strip()
    return text if text.startswith("http") else None


def _image_from_card(card: dict[str, Any]) -> str | None:
    for key in ("image_url", "imageUrl", "img", "image", "artwork_url", "artworkUrl"):
        hit = _http_url(card.get(key))
        if hit:
            return hit
    images = card.get("images")
    if isinstance(images, dict):
        for key in ("large", "small", "url", "default", "front"):
            hit = _http_url(images.get(key))
            if hit:
                return hit
    elif isinstance(images, list):
        for item in images:
            if isinstance(item, str):
                hit = _http_url(item)
            elif isinstance(item, dict):
                hit = _http_url(item.get("url") or item.get("image_url") or item.get("src"))
            else:
                hit = None
            if hit:
                return hit
    return None


def normalize_sealed_hit(card: dict[str, Any]) -> dict[str, Any] | None:
    tcp_external = _external_tcp(card)
    # Opaque JustTCG ids are fine as handles, but must NOT drive TCGPlayer CDN
    # art — wrong numeric ids previously resolved to MTG/FAB singles.
    handle = tcp_external or str(card.get("id") or "").strip() or None
    if not handle:
        return None
    spot = _spot_from_card(card)
    name = str(card.get("name") or "").strip() or f"Sealed {handle}"
    set_name = ""
    set_obj = card.get("set")
    if isinstance(set_obj, dict):
        set_name = str(set_obj.get("name") or "")
    if not set_name:
        set_name = str(card.get("set_name") or card.get("setName") or "")
    image = _image_from_card(card)
    if not image and tcp_external:
        image = tcgplayer_product_image(tcp_external)
    return {
        "card_id": sealed_card_id(handle),
        "name": name,
        "set_name": set_name or None,
        "tcgplayer_id": str(handle),
        "gtin": str(card.get("gtin") or card.get("upc") or "") or None,
        "spot_usd": spot,
        "image_url": image,
        "source": "justtcg",
        "kind": "sealed",
    }


def fetch_sealed_by_gtin(gtin: str) -> dict[str, Any] | None:
    code = re.sub(r"\D", "", str(gtin or ""))
    if len(code) < 8:
        return None
    payload = _client()._get_v2(
        "/cards",
        {
            "gtin": code,
            "include": "price_history.90d",
            "regions": "NA",
            "limit": 5,
        },
    )
    rows = list(payload.get("data") or [])
    # Prefer an exact GTIN hit when present; otherwise first sealed-looking row.
    for row in rows:
        row_gtin = re.sub(r"\D", "", str(row.get("gtin") or row.get("upc") or ""))
        if row_gtin and row_gtin == code:
            return row
    return rows[0] if rows else None


def fetch_sealed_by_tcgplayer_id(tcgplayer_id: str) -> dict[str, Any] | None:
    tid = str(tcgplayer_id or "").strip()
    if not tid:
        return None
    # Prefer v2 (sealed-friendly), then v1 NM helper.
    try:
        payload = _client()._get_v2(
            "/cards",
            {
                "tcgplayer_id": tid,
                "include": "price_history.90d",
                "regions": "NA",
                "limit": 5,
            },
        )
        rows = list(payload.get("data") or [])
        for row in rows:
            external = _external_tcp(row)
            if external and str(external).strip() == tid:
                return row
        if rows:
            return rows[0]
    except Exception as exc:
        LOG.info("v2 sealed by tcgplayer_id failed (%s): %s", tid, exc)
    return _client().fetch_card_by_tcgplayer_id(tid)


def search_sealed_products(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if len(q) < 2:
        return []
    limit = max(1, min(int(limit or 8), 20))
    # Heuristic: append sealed keywords so singles don't dominate.
    sealed_q = q if re.search(r"\b(etb|elite|booster|box|tin|bundle|upc)\b", q, re.I) else f"{q} etb"
    payload = _client()._get_v2(
        "/cards",
        {
            "game": "pokemon",
            "q": sealed_q,
            "include": "price_history.90d",
            "regions": "NA",
            "limit": limit,
        },
    )
    rows = list(payload.get("data") or [])
    hits: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").lower()
        # Prefer clearly sealed-looking titles.
        if any(
            token in name
            for token in (
                "elite trainer",
                "etb",
                "booster box",
                "booster bundle",
                "tin",
                "collection box",
                "upc",
                "premium collection",
            )
        ) or "sealed" in str(row.get("type") or "").lower():
            hits.append(row)
    return hits or rows[:limit]


def quote_sealed(
    *,
    q: str | None = None,
    tcgplayer_id: str | None = None,
    gtin: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return normalized sealed quote hits (may be empty)."""
    cards: list[dict[str, Any]] = []
    if gtin:
        hit = fetch_sealed_by_gtin(gtin)
        if hit:
            cards = [hit]
    elif tcgplayer_id:
        hit = fetch_sealed_by_tcgplayer_id(tcgplayer_id)
        if hit:
            cards = [hit]
    elif q:
        # Bare numeric query → treat as TCP id or GTIN.
        raw = str(q).strip()
        if re.fullmatch(r"\d{6,14}", raw):
            if len(raw) >= 12:
                hit = fetch_sealed_by_gtin(raw)
            else:
                hit = fetch_sealed_by_tcgplayer_id(raw)
            cards = [hit] if hit else []
        else:
            cards = search_sealed_products(raw, limit=limit)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        norm = normalize_sealed_hit(card)
        if not norm:
            continue
        cid = str(norm["card_id"])
        if cid in seen:
            continue
        seen.add(cid)
        out.append(norm)
    return out
