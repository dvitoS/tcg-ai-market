"""Ops spot sniff pack — G0 TCP + eBay automation (M0.2).

JustTCG NM batch + parallel eBay sold medians → per-row verdict
(pass / review / fail). Optional auto-heal quarantines hard fails so ops
only spot-checks the short review list.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

# Spot vs live market / sold median bands.
_OK_PCT = 15.0
_WARN_PCT = 35.0
_EBAY_WORKERS = 4
_EBAY_SOLD_LIMIT = 6


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


def _band_status(*, spot: float | None, live: float | None, delta_pct: float | None) -> str:
    """ok | warn | fail | skip."""
    if live is None or delta_pct is None or spot is None:
        return "skip"
    abs_d = abs(float(delta_pct))
    if abs_d <= _OK_PCT:
        return "ok"
    if abs_d <= _WARN_PCT:
        return "warn"
    return "fail"


# Back-compat aliases used by tests / older callers.
_auto_status = _band_status
_TCP_OK_PCT = _OK_PCT
_TCP_WARN_PCT = _WARN_PCT


def _combine_verdict(
    tcp_status: str,
    ebay_status: str,
    *,
    ebay_usable: bool = True,
) -> str:
    """pass | review | fail — human only needs review (+ spot-check passes)."""
    tcp = str(tcp_status or "skip")
    ebay = str(ebay_status or "skip")
    if tcp == "fail" or ebay == "fail":
        return "fail"
    if tcp == "warn" or ebay == "warn":
        return "review"
    if tcp == "ok" and ebay == "ok":
        return "pass"
    if tcp == "ok" and ebay == "skip":
        # When eBay sold isn't available (no creds / no Insights), TCP-only is enough.
        return "pass" if not ebay_usable else "review"
    if ebay == "ok" and tcp == "skip":
        return "review"
    return "review"


def _card_number_from_id(card_id: str) -> str | None:
    text = str(card_id or "").strip()
    if "-" not in text:
        return None
    number = text.rsplit("-", 1)[-1].strip()
    return number or None


# Name+number (≥120) before we trust a resolved TCP id for auto-fail.
_MIN_TCP_MATCH_SCORE = 120
# Below this, even a "fail" band is treated as review (wrong printing risk).
_STRICT_TCP_FAIL_SCORE = 150


def _resolve_missing_tcp_ids(items: list[dict[str, Any]]) -> dict[str, int]:
    """Fill blank tcgplayer_id via JustTCG search — only strong name+number hits."""
    from justtcg_client import (
        _score_search_row,
        card_tcgplayer_id,
        normalize_card_number,
        pick_nm_variant,
        search_pokemon_card,
        variant_price_usd,
    )

    missing = 0
    resolved = 0
    rejected = 0
    for item in items:
        tid = str(item.get("tcgplayer_id") or "").strip()
        if tid.isdigit():
            item["tcp_match_score"] = item.get("tcp_match_score") or 999
            continue
        missing += 1
        name = str(item.get("name") or "")
        set_name = str(item.get("set_name") or "") or None
        number = _card_number_from_id(str(item.get("card_id") or ""))
        try:
            # Full search (not quick) — number+set disambiguation matters for G0.
            card = search_pokemon_card(
                name=name,
                number=number,
                set_name=set_name,
                quick=False,
            )
        except Exception:
            card = None
        if not card:
            item["skip_reason"] = "no_tcp_id"
            continue
        score = _score_search_row(
            card,
            wanted_name=name.strip().lower(),
            wanted_number=normalize_card_number(number) if number else "",
            wanted_set=(set_name or "").strip().lower(),
        )
        item["tcp_match_score"] = int(score)
        if score < _MIN_TCP_MATCH_SCORE:
            item["skip_reason"] = "weak_tcp_match"
            rejected += 1
            continue
        resolved_tid = card_tcgplayer_id(card)
        if not resolved_tid:
            item["skip_reason"] = "no_tcp_id"
            continue
        item["tcgplayer_id"] = str(resolved_tid)
        item["tcgplayer_url"] = _tcp_product_url(resolved_tid)
        item["tcp_resolved"] = True
        price = variant_price_usd(pick_nm_variant(list(card.get("variants") or [])))
        if price is not None:
            item["tcp_live"] = round(float(price), 4)
        resolved += 1
    return {
        "tcp_missing": missing,
        "tcp_resolved": resolved,
        "tcp_rejected": rejected,
    }


def _enrich_live_tcp(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Batch JustTCG NM lookup; mutate items with tcp_live / tcp_status."""
    summary = {
        "live_checked": False,
        "live_configured": False,
        "auto_ok": 0,
        "auto_warn": 0,
        "auto_fail": 0,
        "auto_skip": 0,
        "tcp_missing": 0,
        "tcp_resolved": 0,
        "tcp_rejected": 0,
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
    except Exception as exc:  # pragma: no cover
        summary["live_error"] = f"import:{exc}"
        for item in items:
            item["tcp_live"] = None
            item["tcp_delta_pct"] = None
            item["tcp_status"] = "skip"
            item["auto_status"] = "skip"
            item["skip_reason"] = "justtcg_import"
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
            item["tcp_status"] = "skip"
            item["auto_status"] = "skip"
            item["skip_reason"] = "justtcg_key_missing"
            summary["auto_skip"] += 1
        return summary

    try:
        resolve_stats = _resolve_missing_tcp_ids(items)
        summary["tcp_missing"] = int(resolve_stats.get("tcp_missing") or 0)
        summary["tcp_resolved"] = int(resolve_stats.get("tcp_resolved") or 0)
        summary["tcp_rejected"] = int(resolve_stats.get("tcp_rejected") or 0)
    except Exception as exc:
        summary["live_error"] = f"resolve:{exc}"[:240]

    tids = [
        str(item.get("tcgplayer_id") or "").strip()
        for item in items
        if str(item.get("tcgplayer_id") or "").strip().isdigit()
    ]
    by_tid: dict[str, float] = {}
    try:
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
            if item.get("tcp_live") is None:
                item["tcp_live"] = None
                item["tcp_delta_pct"] = None
                item["tcp_status"] = "skip"
                item["auto_status"] = "skip"
                item["skip_reason"] = item.get("skip_reason") or "justtcg_batch_error"
                summary["auto_skip"] += 1
        return summary

    for item in items:
        tid = str(item.get("tcgplayer_id") or "").strip()
        live = by_tid.get(tid)
        if live is None and item.get("tcp_live") is not None:
            try:
                live = float(item["tcp_live"])
            except (TypeError, ValueError):
                live = None
        spot = item.get("spot")
        try:
            spot_f = float(spot) if spot is not None else None
        except (TypeError, ValueError):
            spot_f = None
        delta = _pct_delta(spot_f, live)
        status = _band_status(spot=spot_f, live=live, delta_pct=delta)
        item["tcp_live"] = round(live, 4) if live is not None else None
        item["tcp_delta_pct"] = delta
        item["tcp_status"] = status
        item["auto_status"] = status  # legacy field = TCP status
        if status == "skip" and not item.get("skip_reason"):
            item["skip_reason"] = "no_tcp_id" if not tid.isdigit() else "no_tcp_price"
        summary[f"auto_{status}"] = int(summary.get(f"auto_{status}") or 0) + 1

    return summary


def _fetch_one_ebay(item: dict[str, Any]) -> dict[str, Any]:
    from services.ebay_listings import fetch_ebay_sold_comps

    card_id = str(item.get("card_id") or "")
    name = str(item.get("name") or card_id)
    set_name = str(item.get("set_name") or "")
    rows, hint, stats = fetch_ebay_sold_comps(
        card_id=card_id,
        name=name,
        set_name=set_name,
        limit=_EBAY_SOLD_LIMIT,
    )
    is_sold = bool(stats.get("is_sold", 0.0)) and bool(rows)
    median = stats.get("median") if is_sold else None
    try:
        median_f = float(median) if median is not None else None
    except (TypeError, ValueError):
        median_f = None
    n = int(stats.get("n") or 0) if is_sold else 0
    return {
        "card_id": card_id,
        "ebay_median": round(median_f, 4) if median_f is not None else None,
        "ebay_n": n,
        "ebay_is_sold": is_sold,
        "ebay_hint": (hint or None) if not is_sold else None,
    }


def _enrich_ebay_sold(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Parallel eBay sold medians; mutate items with ebay_* + ebay_status."""
    summary = {
        "ebay_checked": False,
        "ebay_configured": False,
        "ebay_ok": 0,
        "ebay_warn": 0,
        "ebay_fail": 0,
        "ebay_skip": 0,
        "ebay_error": None,
    }
    try:
        from ebay_client import ebay_configured
    except Exception as exc:  # pragma: no cover
        summary["ebay_error"] = f"import:{exc}"
        for item in items:
            item["ebay_median"] = None
            item["ebay_delta_pct"] = None
            item["ebay_n"] = 0
            item["ebay_is_sold"] = False
            item["ebay_status"] = "skip"
            summary["ebay_skip"] += 1
        return summary

    configured = bool(ebay_configured())
    summary["ebay_configured"] = configured
    if not configured or not items:
        for item in items:
            item["ebay_median"] = None
            item["ebay_delta_pct"] = None
            item["ebay_n"] = 0
            item["ebay_is_sold"] = False
            item["ebay_status"] = "skip"
            summary["ebay_skip"] += 1
        return summary

    by_id: dict[str, dict[str, Any]] = {}
    try:
        workers = min(_EBAY_WORKERS, max(1, len(items)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_fetch_one_ebay, item) for item in items]
            for fut in as_completed(futures):
                try:
                    row = fut.result()
                    by_id[str(row["card_id"])] = row
                except Exception as exc:
                    summary["ebay_error"] = str(exc)[:240]
        summary["ebay_checked"] = True
    except Exception as exc:
        summary["ebay_error"] = str(exc)[:240]
        for item in items:
            item["ebay_median"] = None
            item["ebay_delta_pct"] = None
            item["ebay_n"] = 0
            item["ebay_is_sold"] = False
            item["ebay_status"] = "skip"
            summary["ebay_skip"] += 1
        return summary

    for item in items:
        meta = by_id.get(str(item.get("card_id") or ""), {})
        median = meta.get("ebay_median")
        spot = item.get("spot")
        try:
            spot_f = float(spot) if spot is not None else None
        except (TypeError, ValueError):
            spot_f = None
        delta = _pct_delta(spot_f, median)
        # Active-only fallback (no true sold) → skip, not a false pass.
        if not meta.get("ebay_is_sold"):
            status = "skip"
            delta = None
            median = None
        else:
            status = _band_status(spot=spot_f, live=median, delta_pct=delta)
        item["ebay_median"] = median
        item["ebay_delta_pct"] = delta
        item["ebay_n"] = int(meta.get("ebay_n") or 0)
        item["ebay_is_sold"] = bool(meta.get("ebay_is_sold"))
        item["ebay_status"] = status
        item["check_ebay"] = status == "ok"
        summary[f"ebay_{status}"] = int(summary.get(f"ebay_{status}") or 0) + 1

    return summary


def _apply_verdicts(
    items: list[dict[str, Any]],
    *,
    ebay_usable: bool = True,
) -> dict[str, int]:
    counts = {"pass": 0, "review": 0, "fail": 0}
    for item in items:
        tcp = str(item.get("tcp_status") or item.get("auto_status") or "skip")
        ebay = str(item.get("ebay_status") or "skip")
        verdict = _combine_verdict(tcp, ebay, ebay_usable=ebay_usable)
        # Resolved-via-search matches that aren't rock-solid must not auto-fail
        # (wrong printing / same-name hit → false quarantine).
        try:
            match_score = int(item.get("tcp_match_score") or 0)
        except (TypeError, ValueError):
            match_score = 0
        if (
            verdict == "fail"
            and bool(item.get("tcp_resolved"))
            and match_score < _STRICT_TCP_FAIL_SCORE
        ):
            verdict = "review"
            item["skip_reason"] = item.get("skip_reason") or "weak_tcp_fail"
            item["notes"] = (
                (item.get("notes") or "") + " weak TCP match→review"
            ).strip()
        item["verdict"] = verdict
        item["check_tcp"] = tcp == "ok"
        counts[verdict] = int(counts.get(verdict) or 0) + 1
    return counts


def _auto_heal_fails(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Quarantine hard-fail rows so they drop off the sure desk."""
    fail_ids = [
        str(item.get("card_id") or "").strip()
        for item in items
        if str(item.get("verdict") or "") == "fail" and str(item.get("card_id") or "").strip()
    ]
    fail_ids = list(dict.fromkeys(fail_ids))
    if not fail_ids:
        return {"healed": 0, "ids": [], "quotes_quarantined": 0}

    from services.spot_heal import heal_poisoned_spots

    result = heal_poisoned_spots(
        mode="null_market",
        limit=len(fail_ids),
        card_ids=fail_ids,
    )
    healed = int(result.get("quotes_quarantined") or result.get("nulled") or 0)
    healed_set = set(fail_ids) if healed else set()
    # Prefer actual ids from heal result when present.
    raw_ids = [str(x) for x in (result.get("ids") or []) if str(x).strip()]
    if raw_ids:
        healed_set = set(raw_ids)

    remaining: list[dict[str, Any]] = []
    for item in items:
        cid = str(item.get("card_id") or "")
        if cid in healed_set:
            item["healed"] = True
            item["notes"] = (item.get("notes") or "") + "auto-healed fail"
            continue
        remaining.append(item)
    items[:] = remaining
    return {
        "healed": len(healed_set),
        "ids": sorted(healed_set),
        "quotes_quarantined": healed,
        "heal_raw": {
            "nulled": int(result.get("nulled") or 0),
            "quotes_quarantined": int(result.get("quotes_quarantined") or 0),
        },
    }


def build_spot_sniff_pack(
    *,
    limit: int = 20,
    live_check: bool = True,
    ebay_check: bool = True,
    auto_heal: bool = True,
) -> dict[str, Any]:
    """Balanced sure UNDER/OVER sample with TCP + eBay auto verdict.

    Default path auto-heals hard fails. Ops only reviews ``verdict=review``
    rows (and optionally spot-checks passes). Gate still needs ≥18/20 pass
    after heal — see ``g0_ready``.
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
                    "tcp_status": "skip",
                    "auto_status": "skip",
                    "tcp_resolved": False,
                    "skip_reason": None,
                    "ebay_median": None,
                    "ebay_delta_pct": None,
                    "ebay_n": 0,
                    "ebay_is_sold": False,
                    "ebay_status": "skip",
                    "verdict": "review",
                    "healed": False,
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
            "tcp_missing": 0,
            "tcp_resolved": 0,
            "tcp_rejected": 0,
            "live_error": None,
        }
    )
    if not live_check:
        for item in items:
            item["tcp_status"] = "skip"
            item["auto_status"] = "skip"

    ebay_summary = (
        _enrich_ebay_sold(items)
        if ebay_check
        else {
            "ebay_checked": False,
            "ebay_configured": False,
            "ebay_ok": 0,
            "ebay_warn": 0,
            "ebay_fail": 0,
            "ebay_skip": len(items),
            "ebay_error": None,
        }
    )
    if not ebay_check:
        for item in items:
            item["ebay_status"] = "skip"

    # eBay usable only when configured AND at least one true sold median landed.
    ebay_usable = bool(ebay_summary.get("ebay_configured")) and int(
        ebay_summary.get("ebay_ok") or 0
    ) + int(ebay_summary.get("ebay_warn") or 0) + int(ebay_summary.get("ebay_fail") or 0) > 0

    verdict_counts = _apply_verdicts(items, ebay_usable=ebay_usable)
    heal_summary = (
        _auto_heal_fails(items)
        if auto_heal
        else {"healed": 0, "ids": [], "quotes_quarantined": 0}
    )
    # Re-count after heal removed fails from items.
    verdict_counts = _apply_verdicts(items, ebay_usable=ebay_usable)

    order = {"fail": 0, "review": 1, "pass": 2}
    items.sort(
        key=lambda it: (
            order.get(str(it.get("verdict") or "review"), 9),
            str(it.get("side") or ""),
            str(it.get("name") or ""),
        )
    )

    passed = int(verdict_counts.get("pass") or 0)
    review = int(verdict_counts.get("review") or 0)
    fail = int(verdict_counts.get("fail") or 0)
    total = max(1, len(items))
    # After auto-heal, ready when no remaining fails and ≥90% pass (18/20).
    g0_ready = fail == 0 and passed >= max(1, int(round(0.9 * total))) and total >= 4

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
        "tcp_missing": int(live_summary.get("tcp_missing") or 0),
        "tcp_resolved": int(live_summary.get("tcp_resolved") or 0),
        "tcp_rejected": int(live_summary.get("tcp_rejected") or 0),
        "live_error": live_summary.get("live_error"),
        "ebay_checked": bool(ebay_summary.get("ebay_checked")),
        "ebay_configured": bool(ebay_summary.get("ebay_configured")),
        "ebay_usable": bool(ebay_usable),
        "ebay_ok": int(ebay_summary.get("ebay_ok") or 0),
        "ebay_warn": int(ebay_summary.get("ebay_warn") or 0),
        "ebay_fail": int(ebay_summary.get("ebay_fail") or 0),
        "ebay_skip": int(ebay_summary.get("ebay_skip") or 0),
        "ebay_error": ebay_summary.get("ebay_error"),
        "verdict_pass": passed,
        "verdict_review": review,
        "verdict_fail": fail,
        "healed_n": int(heal_summary.get("healed") or 0),
        "healed_ids": list(heal_summary.get("ids") or []),
        "g0_ready": bool(g0_ready),
        "instructions": (
            "Auto G0: resolves missing TCGplayer ids, JustTCG NM + eBay sold. "
            "Hard fails auto-heal. Open only review rows. If g0_ready and review "
            "rows smell OK → G0 can pass (still confirm before ads)."
        ),
        "items": items,
    }
