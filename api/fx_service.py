"""USD→EUR FX for Soft Ink dual-currency spots (display only)."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

LOG = logging.getLogger("kestrel.fx")

# Frankfurter (ECB-derived) — no API key.
_FRANKFURTER = "https://api.frankfurter.app/latest?from=USD&to=EUR"
_CACHE_TTL_SECONDS = 6 * 60 * 60
# Stale fallback when offline — roughly mid-2025 ECB ballpark; labeled as fallback.
_FALLBACK_USD_EUR = 0.92

_cache: dict[str, Any] = {"payload": None, "expires": 0.0}


def clear_fx_cache() -> None:
    _cache["payload"] = None
    _cache["expires"] = 0.0


def _fetch_frankfurter() -> dict[str, Any]:
    req = Request(
        _FRANKFURTER,
        headers={"Accept": "application/json", "User-Agent": "kestrel-soft-ink/1.0"},
        method="GET",
    )
    with urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8")
    import json

    data = json.loads(raw)
    rates = data.get("rates") or {}
    rate = float(rates.get("EUR"))
    if rate <= 0:
        raise ValueError("invalid EUR rate")
    return {
        "usd_eur": round(rate, 6),
        "as_of": str(data.get("date") or ""),
        "source": "frankfurter",
        "fallback": False,
    }


def get_usd_eur_quote(*, force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = _cache.get("payload")
    if (
        not force_refresh
        and cached is not None
        and float(_cache.get("expires") or 0) > now
    ):
        return dict(cached)

    try:
        payload = _fetch_frankfurter()
        _cache["payload"] = payload
        _cache["expires"] = now + _CACHE_TTL_SECONDS
        return dict(payload)
    except (URLError, TimeoutError, ValueError, KeyError, TypeError, OSError) as exc:
        LOG.warning("FX fetch failed (%s) — using fallback %.4f", exc, _FALLBACK_USD_EUR)
        payload = {
            "usd_eur": _FALLBACK_USD_EUR,
            "as_of": None,
            "source": "fallback",
            "fallback": True,
        }
        # Shorter TTL on failure so we retry sooner.
        _cache["payload"] = payload
        _cache["expires"] = now + 15 * 60
        return dict(payload)
