"""Ops spot sniff pack — sample sure Radar rows for TCP / eBay checks (M0.2 / G0).

Live JustTCG NM batch (optional) auto-flags rows so ops only deep-checks
warn/fail instead of clicking through all 20 by hand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Spot vs live TCP market: within band → ok; mid → warn; beyond → fail.
_TCP_OK_PCT = 15.0
_TCP_WARN_PCT = 35.0


def _tcp_product_url(tcgplayer_id: Any) -> str | None:
    tid = str(tcgplayer_id or "").strip()
    if not tid.isdigit():
        return None
    return f"https://www.tcgplayer.com/product/{tid}"


def _kestrel_card_path(card_id: str) -> str:
    from urllib.parse import quote

    return f"/cards/{quote(str(card_id), safe='')}"


def _pct_delta(spot: float | None, live: float | None) -> float | None:
    if spot is None or live is None:
        return None
    try:
        s = float(spot)
        live_v = float(live)
    except (TypeError, ValueError):
        return None
    if live_v <= 0 or s < 0:
        return None
    return round(100.0 * (s - live_v) / live_v, 2)


def _auto_status(*, spot: float | None, live: float | None, delta_pct: float | None) -> str:
    """ok | warn | fail | skip — skip when no live TCP price to compare."""
    if live is None or delta_pct is None or spot is None:
        return "skip"
    abs_d = abs(float(delta_pct))
    if abs_d <= _TCP_OK_PCT:
        return "ok"
    if abs_d <= _TCP_WARN_PCT:
        return "warn"
    return "fail"


def _enrich_live_tcp(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Batch JustTCG NM lookup; mutate items with tcp_live / auto_status."""
    summary = {
        "live_checked": False,
        "live_configured": False,
        "auto_ok": 0,
        "auto_warn": 0,
        "auto_fail": 0,
        "auto_skip": 0,
        "live_error": None,
    }
    try:
        from justtcg_client import (
            batch_by_tcgplayer_ids,
            card_tcgplayer_id,
            justtcg_api_key,
            pick_nm_variant,
            variant_price_usd,
        )
    except Exception as exc:  # pragma: no cover - import guard
        summary["live_error"] = f"import:{exc}"
        for item in items:
            item["tcp_live"] = None
            item["tcp_delta_pct"] = None
            item["auto_status"] = "skip"
            summary["auto_skip"] += 1
        return summary

    try:
        key = justtcg_api_key()
    except Exception:
        key = ""
    summary["live_configured"] = bool(key)
    if not key:
        for item in items:
            item["tcp_live"] = None
            item["tcp_delta_pct"] = None
            item["auto_status"] = "skip"
            summary["auto_skip"] += 1
        return summary

    tids = [
        str(item.get("tcgplayer_id") or "").strip()
        for item in items
        if str(item.get("tcgplayer_id") or "").strip().isdigit()
    ]
    by_tid: dict[str, float] = {}
    try:
        # Chunk if pack > batch size (sniff max 40; batch usually ≥40).
        from justtcg_client import JUSTTCG_BATCH_SIZE

        chunk = max(1, int(JUSTTCG_BATCH_SIZE or 40))
        rows: list[dict[str, Any]] = []
        uniq = list(dict.fromkeys(tids))
        for i in range(0, len(uniq), chunk):
            rows.extend(batch_by_tcgplayer_ids(uniq[i : i + chunk]))
        for row in rows:
            tid = card_tcgplayer_id(row)
            if not tid:
                continue
            price = variant_price_usd(pick_nm_variant(list(row.get("variants") or [])))
            if price is not None:
                by_tid[str(tid)] = float(price)
        summary["live_checked"] = True
    except Exception as exc:
        summary["live_error"] = str(exc)[:240]
        for item in items:
            item["tcp_live"] = None
            item["tcp_delta_pct"] = None
            item["auto_status"] = "skip"
            summary["auto_skip"] += 1
        return summary

    for item in items:
        tid = str(item.get("tcgplayer_id") or "").strip()
        live = by_tid.get(tid)
        spot = item.get("spot")
        try:
            spot_f = float(spot) if spot is not None else None
        except (TypeError, ValueError):
            spot_f = None
        delta = _pct_delta(spot_f, live)
        status = _auto_status(spot=spot_f, live=live, delta_pct=delta)
        item["tcp_live"] = round(live, 4) if live is not None else None
        item["tcp_delta_pct"] = delta
        item["auto_status"] = status
        summary[f"auto_{status}"] = int(summary.get(f"auto_{status}") or 0) + 1

    return summary


def build_spot_sniff_pack(*, limit: int = 20, live_check: bool = True) -> dict[str, Any]:
    """Return a balanced sample of sure UNDER/OVER rows for sniffing.

    When ``live_check`` is true and JustTCG is configured, each row gets a
    live NM TCP market compare so ops can prioritize warn/fail first.
    Marketing spend must not launch until a human still marks the pack as
    passing against TCGplayer + eBay sold (auto-ok is assist, not the gate).
    """
    limit = max(4, min(int(limit or 20), 40))
    half = max(2, limit // 2)

    from api.radar_service import build_radar

    radar = build_radar(min_edge=0, limit=half, share_safe=True)
    under = list(radar.get("underpriced") or [])[:half]
    over = list(radar.get("overpriced") or [])[:half]

    items: list[dict[str, Any]] = []
    for side, rows in (("UNDER", under), ("OVER", over)):
        for row in rows:
            card_id = str(row.get("id") or "").strip()
            if not card_id:
                continue
            tcp = row.get("tcgplayer_id")
            items.append(
                {
                    "card_id": card_id,
                    "name": str(row.get("name") or card_id),
                    "set_name": row.get("set_name"),
                    "rarity": row.get("rarity"),
                    "side": side,
                    "spot": row.get("spot") if row.get("spot") is not None else row.get("price"),
                    "fair_price": row.get("fair_price")
                    if row.get("fair_price") is not None
                    else row.get("predicted_price"),
                    "edge_pct": row.get("edge_pct"),
                    "tcgplayer_id": str(tcp) if tcp is not None else None,
                    "tcgplayer_url": _tcp_product_url(tcp),
                    "kestrel_path": _kestrel_card_path(card_id),
                    "tcp_live": None,
                    "tcp_delta_pct": None,
                    "auto_status": "skip",
                    "check_tcp": None,
                    "check_ebay": None,
                    "notes": "",
                }
            )

    live_summary = (
        _enrich_live_tcp(items)
        if live_check
        else {
            "live_checked": False,
            "live_configured": False,
            "auto_ok": 0,
            "auto_warn": 0,
            "auto_fail": 0,
            "auto_skip": len(items),
            "live_error": None,
        }
    )
    if not live_check:
        for item in items:
            item["auto_status"] = "skip"

    # Surface fail/warn first so ops start with the hard ones.
    order = {"fail": 0, "warn": 1, "skip": 2, "ok": 3}
    items.sort(key=lambda it: (order.get(str(it.get("auto_status") or "skip"), 9), it["side"], it["name"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limit": limit,
        "count": len(items),
        "under_n": sum(1 for i in items if i["side"] == "UNDER"),
        "over_n": sum(1 for i in items if i["side"] == "OVER"),
        "board_source": str(radar.get("source") or "empty"),
        "pass_required": True,
        "live_checked": bool(live_summary.get("live_checked")),
        "live_configured": bool(live_summary.get("live_configured")),
        "auto_ok": int(live_summary.get("auto_ok") or 0),
        "auto_warn": int(live_summary.get("auto_warn") or 0),
        "auto_fail": int(live_summary.get("auto_fail") or 0),
        "auto_skip": int(live_summary.get("auto_skip") or 0),
        "live_error": live_summary.get("live_error"),
        "instructions": (
            "Auto TCP live (JustTCG NM) flags fail/warn first — still open TCGplayer + "
            "eBay sold for those rows. Mark pass only if spot is plausible for NM and "
            "the sure side still makes sense. Any hard fail → block marketing spend (G0)."
        ),
        "items": items,
    }
