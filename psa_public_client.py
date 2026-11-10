"""PSA Public API — cert verification + spec population (no market prices).

Docs: https://www.psacard.com/publicapi
Base: https://api.psacard.com/publicapi

Useful for Soft Ink Grading EV gem-rate hints and slab cert lookup.
Does **not** replace JustTCG PSA 9/10 comps (those are sold/print prices).
Free tier is typically ~100 calls/day — cache aggressively.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date
from typing import Any

import requests

from config import _secret

LOG = logging.getLogger("tcg.psa_public")

PSA_PUBLIC_BASE = "https://api.psacard.com/publicapi"
_TIMEOUT = 20
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()

_DAY: str | None = None
_USED = 0
_BUDGET_LOCK = threading.Lock()


class PsaPublicError(RuntimeError):
    """Upstream PSA Public API failure."""


class PsaPublicRateLimitError(PsaPublicError):
    """HTTP 429 or local daily budget exhausted."""


def psa_public_api_token() -> str:
    return (
        _secret("PSA_PUBLIC_API_TOKEN")
        or os.getenv("PSA_PUBLIC_API_TOKEN", "")
        or _secret("PSA_API_TOKEN")
        or os.getenv("PSA_API_TOKEN", "")
        or ""
    ).strip()


def psa_public_configured() -> bool:
    return bool(psa_public_api_token())


def psa_public_daily_budget() -> int:
    """Soft local cap (default 80) under typical free ~100/day."""
    raw = (os.environ.get("PSA_PUBLIC_DAILY_BUDGET") or "80").strip().lower()
    if raw in {"0", "off", "none"}:
        return 0
    if raw in {"unlimited", "inf", "all"}:
        return 10_000
    if raw.isdigit():
        return max(1, min(int(raw), 10_000))
    return 80


def reset_psa_public_budget_for_tests() -> None:
    global _DAY, _USED
    with _BUDGET_LOCK:
        _DAY = None
        _USED = 0
    with _CACHE_LOCK:
        _CACHE.clear()


def _consume_budget() -> None:
    budget = psa_public_daily_budget()
    if budget <= 0:
        raise PsaPublicRateLimitError("PSA Public API daily budget disabled.")
    today = date.today().isoformat()
    global _DAY, _USED
    with _BUDGET_LOCK:
        if _DAY != today:
            _DAY = today
            _USED = 0
        if _USED >= budget:
            raise PsaPublicRateLimitError("PSA Public API daily budget exhausted.")
        _USED += 1


def _cache_get(key: str) -> Any | None:
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if not hit:
            return None
        stamp, payload = hit
        if now - stamp > _CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return None
        return payload


def _cache_set(key: str, payload: Any) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), payload)
        if len(_CACHE) > 512:
            # Drop oldest roughly.
            for old in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:64]:
                _CACHE.pop(old, None)


def _headers() -> dict[str, str]:
    token = psa_public_api_token()
    if not token:
        raise PsaPublicError("PSA_PUBLIC_API_TOKEN is not configured.")
    # PSA docs accept "Bearer <token>" (capital B).
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _get_json(path: str, *, cache_key: str) -> Any:
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    _consume_budget()
    url = f"{PSA_PUBLIC_BASE}{path}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise PsaPublicError(f"PSA Public API transport error: {exc}") from exc
    if resp.status_code == 429:
        raise PsaPublicRateLimitError("PSA Public API rate limited (429).")
    if resp.status_code >= 400:
        raise PsaPublicError(f"PSA Public API HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise PsaPublicError("PSA Public API returned non-JSON") from exc
    _cache_set(cache_key, data)
    return data


def normalize_cert_number(raw: str) -> str:
    text = str(raw or "").strip()
    if "psacard.com/cert/" in text.lower():
        text = text.rstrip("/").rsplit("/", 1)[-1]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits


def get_cert_by_number(cert_number: str) -> dict[str, Any]:
    cert = normalize_cert_number(cert_number)
    if not cert or len(cert) < 4:
        raise PsaPublicError("Invalid PSA cert number.")
    return _get_json(
        f"/cert/GetByCertNumber/{cert}",
        cache_key=f"cert:{cert}",
    )


def get_spec_population(spec_id: int) -> dict[str, Any]:
    sid = int(spec_id)
    if sid <= 0:
        raise PsaPublicError("Invalid PSA SpecID.")
    return _get_json(
        f"/pop/GetPSASpecPopulation/{sid}",
        cache_key=f"pop:{sid}",
    )


def get_cert_images(cert_number: str) -> Any:
    cert = normalize_cert_number(cert_number)
    if not cert:
        raise PsaPublicError("Invalid PSA cert number.")
    return _get_json(
        f"/cert/GetImagesByCertNumber/{cert}",
        cache_key=f"img:{cert}",
    )


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def summarize_population(pop_payload: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten PSASpecPopulationModel into Soft Ink-friendly counts + gem %."""
    empty = {
        "spec_id": None,
        "description": None,
        "total": None,
        "grade9": None,
        "grade10": None,
        "gem_rate_pct": None,
    }
    if not pop_payload:
        return empty
    psa = pop_payload.get("PSAPop") or {}
    total = _int_or_none(psa.get("Total"))
    g9 = _int_or_none(psa.get("Grade9"))
    g10 = _int_or_none(psa.get("Grade10"))
    gem: float | None = None
    if total and total > 0 and g10 is not None:
        gem = round(100.0 * float(g10) / float(total), 2)
    return {
        "spec_id": _int_or_none(pop_payload.get("SpecID")),
        "description": pop_payload.get("Description"),
        "total": total,
        "grade9": g9,
        "grade10": g10,
        "gem_rate_pct": gem,
    }


def lookup_cert_pack(cert_number: str, *, include_pop: bool = True) -> dict[str, Any]:
    """Cert metadata + optional spec population for Grading EV."""
    raw = get_cert_by_number(cert_number)
    cert = raw.get("PSACert") if isinstance(raw, dict) else None
    if not isinstance(cert, dict) or not cert:
        msg = None
        if isinstance(raw, dict):
            msg = raw.get("ServerMessage")
        raise PsaPublicError(str(msg or "No PSA cert data found."))

    spec_id = _int_or_none(cert.get("SpecID"))
    pop_summary = summarize_population(None)
    if include_pop and spec_id:
        try:
            pop_summary = summarize_population(get_spec_population(spec_id))
        except PsaPublicError as exc:
            LOG.info("PSA pop skip for spec %s: %s", spec_id, exc)

    return {
        "configured": True,
        "cert_number": str(cert.get("CertNumber") or normalize_cert_number(cert_number)),
        "spec_id": spec_id,
        "subject": cert.get("Subject"),
        "brand": cert.get("Brand"),
        "category": cert.get("Category"),
        "variety": cert.get("Variety"),
        "year": cert.get("Year") or cert.get("YearIssued"),
        "card_number": cert.get("CardNumber"),
        "grade": cert.get("CardGrade") or cert.get("GradeDescription"),
        "label_type": cert.get("LabelType"),
        "total_population": _int_or_none(cert.get("TotalPopulation")),
        "population_higher": _int_or_none(cert.get("PopulationHigher")),
        "pop_total": pop_summary.get("total"),
        "pop_grade9": pop_summary.get("grade9"),
        "pop_grade10": pop_summary.get("grade10"),
        "pop_description": pop_summary.get("description"),
        "gem_rate_pct": pop_summary.get("gem_rate_pct"),
        "source": "psa_public_api",
    }
