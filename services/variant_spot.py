"""JustTCG variant spots for Soft Ink lots (Phase C4).

Non-NM / non-Normal lots prefer live JustTCG condition×printing prices.
Falls back to coarse NM multipliers when TCP id / variant / key is missing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

LOG = logging.getLogger("tcg.variant_spot")

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 45 * 60
_CACHE_MAX = 512


def clear_variant_spot_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def spot_key(card_id: str, condition: str, printing: str) -> str:
    from services.lot_price_adjust import normalize_condition, normalize_printing

    return (
        f"{str(card_id).strip()}|"
        f"{normalize_condition(condition)}|"
        f"{normalize_printing(printing)}"
    )


def needs_variant_lookup(condition: Any = "NM", printing: Any = "Normal") -> bool:
    from services.lot_price_adjust import normalize_condition, normalize_printing

    return (
        normalize_condition(condition) != "NM"
        or normalize_printing(printing) != "Normal"
    )


def _cache_get(key: str) -> dict[str, Any] | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is None:
            return None
        expires_at, payload = hit
        if expires_at <= now:
            _CACHE.pop(key, None)
            return None
        return dict(payload)


def _cache_put(key: str, payload: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX and key not in _CACHE:
            oldest = next(iter(_CACHE), None)
            if oldest is not None:
                _CACHE.pop(oldest, None)
        _CACHE[key] = (time.monotonic() + _CACHE_TTL_SECONDS, dict(payload))


def _tcp_for_card(card_id: str) -> str | None:
    """Best-effort product id from cards table (no live JustTCG search)."""
    try:
        from database import get_card

        card = get_card(str(card_id))
        if card is not None and getattr(card, "tcgplayer_id", None):
            tcp = str(card.tcgplayer_id).strip()
            return tcp or None
    except Exception as exc:
        LOG.info("variant_spot tcp lookup failed for %s: %s", card_id, exc)
    return None


def _multiplier_payload(
    nm_spot: float | None,
    *,
    condition: str,
    printing: str,
) -> dict[str, Any]:
    from services.lot_price_adjust import adjust_nm_price, lot_price_factor

    factor = lot_price_factor(condition=condition, printing=printing)
    price = adjust_nm_price(nm_spot, condition=condition, printing=printing)
    return {
        "price": price,
        "source": "multiplier",
        "variant_id": None,
        "price_factor": factor,
        "tcgplayer_id": None,
    }


def resolve_variant_spots(
    requests: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Batch-resolve variant spots for Soft Ink lots.

    Each request: {card_id, condition, printing, nm_spot?}.
    Returns spot_key → {price, source, variant_id, price_factor, tcgplayer_id}.
    """
    from config import JUSTTCG_BATCH_SIZE
    from services.lot_price_adjust import (
        lot_price_factor,
        normalize_condition,
        normalize_printing,
    )

    out: dict[str, dict[str, Any]] = {}
    if not requests:
        return out

    pending_fetch: list[dict[str, Any]] = []
    seen_tcp_keys: set[str] = set()

    for raw in requests:
        card_id = str(raw.get("card_id") or "").strip()
        if not card_id or card_id.startswith("sealed:"):
            continue
        condition = normalize_condition(raw.get("condition") or "NM")
        printing = normalize_printing(raw.get("printing") or "Normal")
        key = spot_key(card_id, condition, printing)
        if key in out:
            continue

        nm_spot = raw.get("nm_spot")
        try:
            nm_spot_f = float(nm_spot) if nm_spot is not None else None
        except (TypeError, ValueError):
            nm_spot_f = None

        if not needs_variant_lookup(condition, printing):
            factor = lot_price_factor(condition=condition, printing=printing)
            out[key] = {
                "price": nm_spot_f,
                "source": "board",
                "variant_id": None,
                "price_factor": factor,
                "tcgplayer_id": None,
            }
            continue

        cached = _cache_get(key)
        if cached is not None:
            out[key] = cached
            continue

        tcp = _tcp_for_card(card_id)
        if not tcp:
            payload = _multiplier_payload(
                nm_spot_f, condition=condition, printing=printing
            )
            out[key] = payload
            continue

        tcp_key = f"{tcp}|{condition}|{printing}"
        pending_fetch.append(
            {
                "card_id": card_id,
                "key": key,
                "tcp_key": tcp_key,
                "tcgplayerId": tcp,
                "condition": condition,
                "printing": printing,
                "nm_spot": nm_spot_f,
            }
        )
        seen_tcp_keys.add(tcp_key)

    if not pending_fetch:
        return out

    try:
        from justtcg_client import (
            JustTCGRateLimitError,
            batch_variant_lookups,
            card_tcgplayer_id,
            justtcg_api_key,
            pick_variant,
            variant_price_usd,
        )
    except Exception as exc:
        LOG.info("variant_spot import failed: %s", exc)
        for item in pending_fetch:
            payload = _multiplier_payload(
                item.get("nm_spot"),
                condition=item["condition"],
                printing=item["printing"],
            )
            out[item["key"]] = payload
        return out

    if not justtcg_api_key():
        for item in pending_fetch:
            payload = _multiplier_payload(
                item.get("nm_spot"),
                condition=item["condition"],
                printing=item["printing"],
            )
            out[item["key"]] = payload
        return out

    # Deduplicate by tcp|cond|print for the JustTCG batch body.
    unique_items: list[dict[str, Any]] = []
    tcp_to_rows: dict[str, list[dict[str, Any]]] = {}
    for item in pending_fetch:
        tcp_to_rows.setdefault(item["tcp_key"], []).append(item)
        if len(unique_items) < len(seen_tcp_keys):
            if not any(
                u["tcgplayerId"] == item["tcgplayerId"]
                and u["condition"] == item["condition"]
                and u["printing"] == item["printing"]
                for u in unique_items
            ):
                unique_items.append(
                    {
                        "tcgplayerId": item["tcgplayerId"],
                        "condition": item["condition"],
                        "printing": item["printing"],
                    }
                )

    by_tcp_variant: dict[str, dict[str, Any]] = {}
    batch_size = max(1, int(JUSTTCG_BATCH_SIZE or 20))
    try:
        for i in range(0, len(unique_items), batch_size):
            chunk = unique_items[i : i + batch_size]
            rows = batch_variant_lookups(chunk)
            # Index returned cards by tcgplayerId; pick matching variant.
            by_tcp: dict[str, dict[str, Any]] = {}
            for row in rows:
                tid = card_tcgplayer_id(row) or ""
                if tid:
                    by_tcp[tid] = row
            for req in chunk:
                tid = str(req["tcgplayerId"])
                card = by_tcp.get(tid)
                if not card:
                    continue
                variant = pick_variant(
                    list(card.get("variants") or []),
                    condition=req["condition"],
                    printing=req["printing"],
                )
                price = variant_price_usd(variant)
                if price is None:
                    continue
                variant_id = None
                if variant:
                    variant_id = (
                        str(variant.get("id") or variant.get("uuid") or "").strip()
                        or None
                    )
                tcp_key = f"{tid}|{req['condition']}|{req['printing']}"
                by_tcp_variant[tcp_key] = {
                    "price": float(price),
                    "source": "justtcg_variant",
                    "variant_id": variant_id,
                    "tcgplayer_id": tid,
                }
    except JustTCGRateLimitError:
        LOG.warning("variant_spot rate-limited — falling back to multipliers")
    except Exception as exc:
        LOG.info("variant_spot batch failed: %s", exc)

    for item in pending_fetch:
        hit = by_tcp_variant.get(item["tcp_key"])
        if hit is not None:
            nm = item.get("nm_spot")
            factor = lot_price_factor(
                condition=item["condition"], printing=item["printing"]
            )
            try:
                if nm is not None and float(nm) > 0:
                    factor = float(hit["price"]) / float(nm)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
            payload = {
                **hit,
                "price_factor": float(factor),
            }
            _cache_put(item["key"], payload)
            out[item["key"]] = payload
        else:
            payload = _multiplier_payload(
                item.get("nm_spot"),
                condition=item["condition"],
                printing=item["printing"],
            )
            out[item["key"]] = payload

    return out
