"""Sinkronizira NM cijene + history s JustTCG u Supabase (Phase A).

Paid Soft Ink tier: 100 cards/req, 50/min, 1000/day, 10k/month.
Prefer tcgplayer_id batch POSTs (≈1 req / 100 cards) over set pagination.

PkmnPrices (``PKMN_API_KEY``) fills cards JustTCG leaves empty — capped by
``PKMN_NIGHTLY_MAX_CARDS``. JustTCG stays primary until cutover checklist green.
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

from config import (
    JUSTTCG_BATCH_SIZE,
    PKMN_NIGHTLY_MAX_CARDS,
    PKMN_NIGHTLY_PRIMARY_MAX_CARDS,
    PKMN_NIGHTLY_TCP_RESOLVE_MAX,
    catalog_sets,
)
from database import (
    distinct_history_card_ids,
    init_db,
    list_cards,
    list_cards_for_sync,
    replace_card_history,
    table_count,
    update_card_market_price,
    update_card_tcgplayer_id,
)
from justtcg_client import (
    JustTCGRateLimitError,
    batch_by_tcgplayer_ids,
    card_tcgplayer_id,
    fetch_set_cards_page,
    history_points_from_variant,
    justtcg_api_key,
    justtcg_request_count,
    list_pokemon_sets,
    normalize_card_number,
    pick_nm_variant,
    resolve_set_id,
    variant_price_usd,
)
from services.spot_sanity import is_absurd_spot_jump


def pkmn_nightly_card_budget(*, primary: bool = False) -> int:
    """Max cards that may hit PkmnPrices history this nightly (0 = off).

    ``primary=True`` when JustTCG key is absent — uses
    ``PKMN_NIGHTLY_PRIMARY_MAX_CARDS`` (default 500) unless overridden.
    """
    if primary:
        raw = (os.environ.get("PKMN_NIGHTLY_PRIMARY_MAX_CARDS") or "").strip().lower()
        if raw in {"0", "off", "none"}:
            return 0
        if raw.isdigit():
            return max(0, min(int(raw), 5000))
        # Fall through to shared override, then primary default.
        shared = (os.environ.get("PKMN_NIGHTLY_MAX_CARDS") or "").strip().lower()
        if shared.isdigit():
            return max(0, min(int(shared), 5000))
        return max(0, int(PKMN_NIGHTLY_PRIMARY_MAX_CARDS))

    raw = (os.environ.get("PKMN_NIGHTLY_MAX_CARDS") or "").strip().lower()
    if raw in {"0", "off", "none"}:
        return 0
    if raw.isdigit():
        return max(0, min(int(raw), 5000))
    return max(0, int(PKMN_NIGHTLY_MAX_CARDS))


def _known_unmatched_set_codes() -> set[str]:
    """Skip sets that already failed JustTCG match on a prior nightly."""
    try:
        from services.spot_qa import load_spot_qa_snapshot

        snap = load_spot_qa_snapshot() or {}
    except Exception:
        return set()
    codes = {
        str(c).strip()
        for c in list(snap.get("unmatched_set_codes") or [])
        if str(c).strip()
    }
    for row in list(snap.get("unmatched_sets_sample") or []):
        if isinstance(row, dict):
            code = str(row.get("set_code") or "").strip()
            if code:
                codes.add(code)
    return codes


def _index_db_cards() -> dict[str, list]:
    """set_code -> [(normalized_number, Card), ...]."""
    cards = list_cards(limit=None, order_price_desc=False)
    by_set: dict[str, list] = defaultdict(list)
    for card in cards:
        if "-" not in str(card.id):
            continue
        set_code, number = str(card.id).rsplit("-", 1)
        by_set[set_code].append((normalize_card_number(number), card))
    return by_set


def _match_card(by_set: dict[str, list], set_code: str, just_number: str):
    wanted = normalize_card_number(just_number).lower()
    for number, card in by_set.get(set_code, []):
        if number.lower() == wanted:
            return card
    return None


def _display_set_name(set_code: str, cards: list) -> str:
    """Prefer real card.set_name majority over bare set_code / curated pin."""
    counts: Counter[str] = Counter()
    for _n, card in cards:
        name = str(getattr(card, "set_name", None) or "").strip()
        if name and name.lower() != set_code.lower():
            counts[name] += 1
    if counts:
        return counts.most_common(1)[0][0]
    name_by_id = {sid: name for sid, name in catalog_sets()}
    return name_by_id.get(set_code, set_code)


def _sets_prioritized_by_coverage(by_set: dict[str, list]) -> list[tuple[str, str]]:
    """Prefer sets with more cards missing price_history (fill gaps first)."""
    try:
        have_history = distinct_history_card_ids()
    except Exception as exc:
        # Never abort the whole JustTCG sync on a coverage probe timeout.
        print(f"set coverage probe failed ({exc}) — using catalog order", file=sys.stderr)
        return [
            (set_code, _display_set_name(set_code, cards))
            for set_code, cards in sorted(by_set.items(), key=lambda item: item[0])
        ]
    scored: list[tuple[int, str, str]] = []
    for set_code, cards in by_set.items():
        missing = sum(1 for _n, card in cards if str(card.id) not in have_history)
        scored.append((missing, set_code, _display_set_name(set_code, cards)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(sid, name) for _m, sid, name in scored]


def _ingest_card_row(
    card,
    row: dict,
    *,
    have_history: set[str],
    matched_ids: set[str],
    forbid_spot_keys: set[float] | None = None,
) -> tuple[str, int]:
    """Apply one JustTCG card payload. Returns (status, history_rows_written).

    status: ok | skip_weak | skip_empty | skip_dup | skip_absurd | skip_poison
    """
    if card.id in matched_ids:
        return "skip_dup", 0
    variant = pick_nm_variant(list(row.get("variants") or []))
    points = history_points_from_variant(variant)
    price = variant_price_usd(variant)
    tcp = card_tcgplayer_id(row)
    if not points and price is None:
        return "skip_empty", 0

    prior = getattr(card, "market_price", None)
    tip = None
    if points:
        try:
            tip = float(points[-1]["price"])
        except (TypeError, ValueError, KeyError, IndexError):
            tip = None
    if forbid_spot_keys:
        banned = {round(float(k), 2) for k in forbid_spot_keys}
        for candidate in (price, tip):
            if candidate is None:
                continue
            try:
                if round(float(candidate), 2) in banned:
                    return "skip_poison", 0
            except (TypeError, ValueError):
                pass
    if is_absurd_spot_jump(price, prior) or is_absurd_spot_jump(tip, prior):
        return "skip_absurd", 0
    if tip is not None and price is not None and is_absurd_spot_jump(price, tip):
        # Spot and history tip disagree wildly — refuse both writes.
        return "skip_absurd", 0

    written = 0
    if points:
        # Never wipe a multi-day series with spot-only / tiny payloads.
        min_points = 7
        already = str(card.id) in have_history
        if len(points) < min_points and already:
            if price is not None:
                update_card_market_price(card.id, price, tcgplayer_id=tcp)
            return "skip_weak", 0
        written = replace_card_history(card.id, points)
        have_history.add(str(card.id))
    if price is not None:
        update_card_market_price(card.id, price, tcgplayer_id=tcp)
    matched_ids.add(card.id)
    return "ok", written


def _ingest_pkmn_fallback(
    card,
    *,
    have_history: set[str],
    matched_ids: set[str],
    forbid_spot_keys: set[float] | None = None,
) -> tuple[str, int]:
    """Write NM history from PkmnPrices. Raises PkmnPricesRateLimitError."""
    if card.id in matched_ids:
        return "skip_dup", 0
    tcp = str(getattr(card, "tcgplayer_id", None) or "").strip()
    if not tcp:
        return "skip_empty", 0

    from pkmnprices_client import (
        nm_history_for_tcgplayer_id,
        pkmnprices_configured,
    )

    if not pkmnprices_configured():
        return "skip_no_key", 0

    points = nm_history_for_tcgplayer_id(tcp, period="90d", limit=120)
    if not points:
        return "skip_empty", 0

    tip = None
    try:
        tip = float(points[-1]["price"])
    except (TypeError, ValueError, KeyError, IndexError):
        tip = None
    price = tip
    prior = getattr(card, "market_price", None)

    if forbid_spot_keys:
        banned = {round(float(k), 2) for k in forbid_spot_keys}
        for candidate in (price, tip):
            if candidate is None:
                continue
            try:
                if round(float(candidate), 2) in banned:
                    return "skip_poison", 0
            except (TypeError, ValueError):
                pass
    if is_absurd_spot_jump(price, prior) or is_absurd_spot_jump(tip, prior):
        return "skip_absurd", 0

    min_points = 7
    already = str(card.id) in have_history
    if len(points) < min_points and already:
        if price is not None:
            update_card_market_price(card.id, price, tcgplayer_id=tcp)
        return "skip_weak", 0

    written = replace_card_history(card.id, points)
    have_history.add(str(card.id))
    if price is not None:
        update_card_market_price(card.id, price, tcgplayer_id=tcp)
    matched_ids.add(card.id)
    return "ok", written


def _try_pkmn_fallback(
    card,
    *,
    have_history: set[str],
    matched_ids: set[str],
    pkmn_budget: int,
    pkmn_used: list[int],
    forbid_spot_keys: set[float] | None = None,
) -> tuple[str, int]:
    """Budget-gated PkmnPrices fallback. Returns (status, written)."""
    if pkmn_budget <= 0 or pkmn_used[0] >= pkmn_budget:
        return "skip_budget", 0
    if card.id in matched_ids:
        return "skip_dup", 0
    from pkmnprices_client import PkmnPricesRateLimitError, pkmnprices_configured

    if not pkmnprices_configured():
        return "skip_no_key", 0
    pkmn_used[0] += 1
    try:
        return _ingest_pkmn_fallback(
            card,
            have_history=have_history,
            matched_ids=matched_ids,
            forbid_spot_keys=forbid_spot_keys,
        )
    except PkmnPricesRateLimitError:
        print(
            f"PkmnPrices rate/credit stop after {pkmn_used[0]} cards.",
            file=sys.stderr,
        )
        # Exhaust budget so later cards skip without more HTTP.
        pkmn_used[0] = pkmn_budget
        return "skip_rate", 0
    except Exception as exc:
        print(f"  PkmnPrices {getattr(card, 'id', '?')}: {exc}", file=sys.stderr)
        return "skip_empty", 0


def _pkmn_tcp_resolve_budget() -> int:
    raw = (os.environ.get("PKMN_NIGHTLY_TCP_RESOLVE_MAX") or "").strip().lower()
    if raw in {"0", "off", "none"}:
        return 0
    if raw.isdigit():
        return max(0, min(int(raw), 2000))
    return max(0, int(PKMN_NIGHTLY_TCP_RESOLVE_MAX))


def _card_number_from_id(card_id: str) -> str | None:
    text = str(card_id or "")
    if "-" not in text:
        return None
    return normalize_card_number(text.rsplit("-", 1)[-1]) or None


def sync_pkmn_price_history(*, limit: int | None = None) -> dict[str, int]:
    """PkmnPrices-primary NM drip (no JustTCG).

    1. Cards that already have ``tcgplayer_id``
    2. Path-B substitute: resolve missing TCP via public TCGplayer search
       (capped), persist id, then PkmnPrices history ingest
    """
    from backfill_tcgplayer_ids import resolve_tcgplayer_id_from_search
    from pkmnprices_client import pkmnprices_configured

    if not pkmnprices_configured():
        raise RuntimeError("PKMN_API_KEY nije postavljen.")

    init_db()
    targets = list_cards_for_sync(limit=limit)
    with_tcp = [
        c
        for c in targets
        if str(getattr(c, "tcgplayer_id", None) or "").strip()
    ]
    without_tcp = [
        c
        for c in targets
        if not str(getattr(c, "tcgplayer_id", None) or "").strip()
    ]
    updated = skipped = saved = 0
    tcp_resolved = tcp_resolve_failed = 0
    pkmn_budget = pkmn_nightly_card_budget(primary=True)
    tcp_resolve_budget = _pkmn_tcp_resolve_budget()
    pkmn_used = [0]
    matched_ids: set[str] = set()
    have_history = distinct_history_card_ids()
    print(
        f"PkmnPrices primary sync: {len(with_tcp)} with tcp, "
        f"{len(without_tcp)} without "
        f"(of {len(targets)} prioritized, pkmn_budget={pkmn_budget}, "
        f"tcp_resolve_budget={tcp_resolve_budget})"
    )
    for card in with_tcp:
        if limit is not None and updated >= limit:
            break
        if pkmn_used[0] >= pkmn_budget:
            skipped += 1
            continue
        status, written = _try_pkmn_fallback(
            card,
            have_history=have_history,
            matched_ids=matched_ids,
            pkmn_budget=pkmn_budget,
            pkmn_used=pkmn_used,
        )
        if status == "ok":
            updated += 1
            saved += written
            print(f"  OK {card.id} · pkmn-primary · {written} history pts")
        else:
            skipped += 1

    # Path-B substitute — fill missing TCP then ingest (JustTCG set-walk replacement).
    for card in without_tcp:
        if limit is not None and updated >= limit:
            break
        if tcp_resolved + tcp_resolve_failed >= tcp_resolve_budget:
            skipped += 1
            continue
        if pkmn_used[0] >= pkmn_budget:
            skipped += 1
            continue
        number = _card_number_from_id(str(card.id))
        try:
            tid, score = resolve_tcgplayer_id_from_search(
                name=str(getattr(card, "name", "") or ""),
                number=number,
                set_name=str(getattr(card, "set_name", "") or "") or None,
                min_score=120,
            )
        except Exception as exc:
            print(f"  TCP resolve {card.id}: {exc}", file=sys.stderr)
            tid, score = None, 0
        if not tid:
            tcp_resolve_failed += 1
            skipped += 1
            continue
        try:
            update_card_tcgplayer_id(str(card.id), tid)
        except Exception as exc:
            print(f"  TCP persist {card.id}: {exc}", file=sys.stderr)
            tcp_resolve_failed += 1
            skipped += 1
            continue
        try:
            card.tcgplayer_id = tid
        except Exception:
            pass
        tcp_resolved += 1
        status, written = _try_pkmn_fallback(
            card,
            have_history=have_history,
            matched_ids=matched_ids,
            pkmn_budget=pkmn_budget,
            pkmn_used=pkmn_used,
        )
        if status == "ok":
            updated += 1
            saved += written
            print(
                f"  OK {card.id} · pkmn-pathb tcp={tid} score={score} · "
                f"{written} history pts"
            )
        else:
            skipped += 1

    total = table_count("price_history")
    payload = {
        "updated": updated,
        "skipped": skipped,
        "saved": saved,
        "total_history": int(total),
        "unmatched_sets": [],
        "unmatched_sets_count": 0,
        "justtcg_requests": 0,
        "batch_updated": 0,
        "pkmn_updated": updated,
        "pkmn_saved": saved,
        "pkmn_attempted": pkmn_used[0],
        "pkmn_primary": True,
        "tcp_resolved": tcp_resolved,
        "tcp_resolve_failed": tcp_resolve_failed,
    }
    print(
        f"PkmnPrices primary gotovo: updated={updated} skipped={skipped} "
        f"saved_rows={saved} total_history={payload['total_history']} "
        f"pkmn_attempted={payload['pkmn_attempted']} "
        f"tcp_resolved={tcp_resolved} tcp_resolve_failed={tcp_resolve_failed}"
    )
    return payload


def sync_justtcg_for_card_ids(
    card_ids: list[str],
    *,
    forbid_spot_keys: set[float] | None = None,
) -> dict[str, int]:
    """Targeted JustTCG batch ingest for an explicit card-id allowlist.

    When JustTCG key is missing, falls back to PkmnPrices for TCP cards (heal cutover).
    """
    init_db()
    wanted = [str(cid).strip() for cid in card_ids if str(cid).strip()]
    if not wanted:
        return {
            "updated": 0,
            "skipped": 0,
            "saved": 0,
            "skip_poison": 0,
            "skip_absurd": 0,
            "justtcg_requests": justtcg_request_count(),
        }

    by_id = {str(c.id): c for c in list_cards() if str(c.id) in set(wanted)}
    with_tcp = [
        c
        for cid in wanted
        if (c := by_id.get(cid)) is not None
        and str(getattr(c, "tcgplayer_id", None) or "").strip()
    ]
    tcp_to_card = {
        str(c.tcgplayer_id).strip(): c
        for c in with_tcp
        if str(getattr(c, "tcgplayer_id", None) or "").strip()
    }
    updated = skipped = saved = skip_poison = skip_absurd = 0
    pkmn_updated = pkmn_saved = 0
    pkmn_budget = pkmn_nightly_card_budget(primary=not bool(justtcg_api_key()))
    pkmn_used = [0]
    matched_ids: set[str] = set()
    have_history = distinct_history_card_ids()
    tcp_ids = list(tcp_to_card.keys())

    if not justtcg_api_key():
        for tid in tcp_ids:
            card = tcp_to_card.get(tid)
            if card is None:
                continue
            p_status, p_written = _try_pkmn_fallback(
                card,
                have_history=have_history,
                matched_ids=matched_ids,
                pkmn_budget=pkmn_budget,
                pkmn_used=pkmn_used,
                forbid_spot_keys=forbid_spot_keys,
            )
            if p_status == "ok":
                updated += 1
                pkmn_updated += 1
                saved += p_written
                pkmn_saved += p_written
            else:
                skipped += 1
                if p_status == "skip_poison":
                    skip_poison += 1
                elif p_status == "skip_absurd":
                    skip_absurd += 1
        return {
            "updated": updated,
            "skipped": skipped,
            "saved": saved,
            "skip_poison": skip_poison,
            "skip_absurd": skip_absurd,
            "targeted": len(wanted),
            "with_tcgplayer_id": len(tcp_ids),
            "justtcg_requests": 0,
            "pkmn_updated": pkmn_updated,
            "pkmn_saved": pkmn_saved,
            "pkmn_attempted": pkmn_used[0],
            "pkmn_primary": True,
        }

    for i in range(0, len(tcp_ids), JUSTTCG_BATCH_SIZE):
        chunk = tcp_ids[i : i + JUSTTCG_BATCH_SIZE]
        try:
            rows = batch_by_tcgplayer_ids(chunk)
        except JustTCGRateLimitError:
            break
        except Exception as exc:
            print(f"  heal batch offset={i} greška: {exc}", file=sys.stderr)
            continue
        seen_tcp: set[str] = set()
        for row in rows:
            tid = card_tcgplayer_id(row) or ""
            card = tcp_to_card.get(tid)
            if card is None:
                continue
            seen_tcp.add(tid)
            status, written = _ingest_card_row(
                card,
                row,
                have_history=have_history,
                matched_ids=matched_ids,
                forbid_spot_keys=forbid_spot_keys,
            )
            if status == "ok":
                updated += 1
                saved += written
            elif status == "skip_empty":
                p_status, p_written = _try_pkmn_fallback(
                    card,
                    have_history=have_history,
                    matched_ids=matched_ids,
                    pkmn_budget=pkmn_budget,
                    pkmn_used=pkmn_used,
                    forbid_spot_keys=forbid_spot_keys,
                )
                if p_status == "ok":
                    updated += 1
                    pkmn_updated += 1
                    saved += p_written
                    pkmn_saved += p_written
                else:
                    skipped += 1
                    if p_status == "skip_poison":
                        skip_poison += 1
                    elif p_status == "skip_absurd":
                        skip_absurd += 1
            elif status == "skip_poison":
                skip_poison += 1
                skipped += 1
            elif status == "skip_absurd":
                skip_absurd += 1
                skipped += 1
            elif status == "skip_weak":
                skipped += 1
        for tid in chunk:
            if tid in seen_tcp:
                continue
            card = tcp_to_card.get(tid)
            if card is None or card.id in matched_ids:
                continue
            p_status, p_written = _try_pkmn_fallback(
                card,
                have_history=have_history,
                matched_ids=matched_ids,
                pkmn_budget=pkmn_budget,
                pkmn_used=pkmn_used,
                forbid_spot_keys=forbid_spot_keys,
            )
            if p_status == "ok":
                updated += 1
                pkmn_updated += 1
                saved += p_written
                pkmn_saved += p_written
            else:
                skipped += 1
                if p_status == "skip_poison":
                    skip_poison += 1
                elif p_status == "skip_absurd":
                    skip_absurd += 1
    return {
        "updated": updated,
        "skipped": skipped,
        "saved": saved,
        "skip_poison": skip_poison,
        "skip_absurd": skip_absurd,
        "targeted": len(wanted),
        "with_tcgplayer_id": len(tcp_ids),
        "justtcg_requests": justtcg_request_count(),
        "pkmn_updated": pkmn_updated,
        "pkmn_saved": pkmn_saved,
        "pkmn_attempted": pkmn_used[0],
    }


def sync_justtcg_price_history(*, limit: int | None = None) -> dict[str, int]:
    """Live sync: prefer tcgplayerId batches; set pagination only as fallback."""
    if not justtcg_api_key():
        raise RuntimeError("JUSTTCG_API_KEY nije postavljen.")

    init_db()
    by_set = _index_db_cards()
    if not by_set:
        print("Nema karata u bazi. Prvo uvezi katalog (main.py / nightly catalog).")
        return {
            "updated": 0,
            "skipped": 0,
            "saved": 0,
            "total_history": 0,
            "unmatched_sets": [],
            "unmatched_sets_count": 0,
            "justtcg_requests": 0,
            "batch_updated": 0,
        }

    updated = skipped = saved = 0
    batch_updated = 0
    pkmn_updated = pkmn_saved = 0
    pkmn_budget = pkmn_nightly_card_budget()
    pkmn_used = [0]
    set_cache: dict[str, str] = {}
    matched_ids: set[str] = set()
    unmatched_sets: list[dict[str, str]] = []
    unmatched_seen: set[str] = set()
    have_history = distinct_history_card_ids()
    known_unmatched = _known_unmatched_set_codes()

    def _stats_payload() -> dict:
        total = table_count("price_history")
        return {
            "updated": updated,
            "skipped": skipped,
            "saved": saved,
            "total_history": int(total),
            "unmatched_sets": unmatched_sets,
            "unmatched_sets_count": len(unmatched_sets),
            "justtcg_requests": justtcg_request_count(),
            "batch_updated": batch_updated,
            "pkmn_updated": pkmn_updated,
            "pkmn_saved": pkmn_saved,
            "pkmn_attempted": pkmn_used[0],
        }

    # --- Path A: tcgplayer_id batches (≈1 req / 100 cards) ---
    targets = list_cards_for_sync(limit=limit)
    with_tcp = [
        c
        for c in targets
        if str(getattr(c, "tcgplayer_id", None) or "").strip()
    ]
    tcp_to_card = {
        str(c.tcgplayer_id).strip(): c
        for c in with_tcp
        if str(getattr(c, "tcgplayer_id", None) or "").strip()
    }
    tcp_ids = list(tcp_to_card.keys())
    print(
        f"JustTCG batch sync: {len(tcp_ids)} cards with tcgplayer_id "
        f"(of {len(targets)} prioritized, batch={JUSTTCG_BATCH_SIZE}); "
        f"PkmnPrices fallback budget={pkmn_budget}"
    )
    for i in range(0, len(tcp_ids), JUSTTCG_BATCH_SIZE):
        if limit is not None and updated >= limit:
            break
        chunk = tcp_ids[i : i + JUSTTCG_BATCH_SIZE]
        try:
            rows = batch_by_tcgplayer_ids(chunk)
        except JustTCGRateLimitError:
            print(
                f"JustTCG rate/budget stop pri batch "
                f"(requests={justtcg_request_count()}).",
                file=sys.stderr,
            )
            return _stats_payload()
        except Exception as exc:
            print(f"  batch offset={i} greška: {exc}", file=sys.stderr)
            continue

        seen_tcp: set[str] = set()
        for row in rows:
            tid = card_tcgplayer_id(row) or ""
            card = tcp_to_card.get(tid)
            if card is None:
                continue
            seen_tcp.add(tid)
            status, written = _ingest_card_row(
                card,
                row,
                have_history=have_history,
                matched_ids=matched_ids,
            )
            if status == "ok":
                updated += 1
                batch_updated += 1
                saved += written
                print(f"  OK {card.id} · batch · {written} history pts")
            elif status == "skip_empty":
                p_status, p_written = _try_pkmn_fallback(
                    card,
                    have_history=have_history,
                    matched_ids=matched_ids,
                    pkmn_budget=pkmn_budget,
                    pkmn_used=pkmn_used,
                )
                if p_status == "ok":
                    updated += 1
                    pkmn_updated += 1
                    saved += p_written
                    pkmn_saved += p_written
                    print(f"  OK {card.id} · pkmn · {p_written} history pts")
                else:
                    skipped += 1
            elif status in {"skip_weak", "skip_absurd"}:
                skipped += 1
            if limit is not None and updated >= limit:
                payload = _stats_payload()
                print(
                    f"JustTCG limit hit via batch: updated={updated} "
                    f"requests={payload['justtcg_requests']} "
                    f"pkmn={payload['pkmn_updated']}"
                )
                return payload

        for tid in chunk:
            if limit is not None and updated >= limit:
                break
            if tid in seen_tcp:
                continue
            card = tcp_to_card.get(tid)
            if card is None or card.id in matched_ids:
                continue
            p_status, p_written = _try_pkmn_fallback(
                card,
                have_history=have_history,
                matched_ids=matched_ids,
                pkmn_budget=pkmn_budget,
                pkmn_used=pkmn_used,
            )
            if p_status == "ok":
                updated += 1
                pkmn_updated += 1
                saved += p_written
                pkmn_saved += p_written
                print(f"  OK {card.id} · pkmn-miss · {p_written} history pts")
            else:
                skipped += 1

    if limit is not None and updated >= limit:
        payload = _stats_payload()
        print(
            f"JustTCG gotovo (batch only): updated={updated} "
            f"requests={payload['justtcg_requests']} "
            f"pkmn={payload['pkmn_updated']}"
        )
        return payload

    # --- Path B: set pagination only for remaining gaps without tcp ---
    remaining = 0 if limit is None else max(0, int(limit) - updated)
    if remaining == 0 and limit is not None:
        return _stats_payload()

    ordered_sets = _sets_prioritized_by_coverage(by_set)
    if known_unmatched:
        print(
            f"Skipping {len(known_unmatched)} previously unmatched JustTCG sets"
        )

    catalog_rows: list | None
    try:
        catalog_rows = list_pokemon_sets()
        print(f"JustTCG set catalog: {len(catalog_rows)} rows (fallback path)")
    except JustTCGRateLimitError:
        print("JustTCG rate/budget stop pri list_pokemon_sets.", file=sys.stderr)
        return _stats_payload()
    except Exception as exc:
        print(
            f"JustTCG list_pokemon_sets failed ({exc}) — per-set q= fallback",
            file=sys.stderr,
        )
        catalog_rows = None

    print(
        "JustTCG set fallback — missing history first: %s"
        % ", ".join(f"{n}({c})" for c, n in ordered_sets[:40])
        + ("…" if len(ordered_sets) > 40 else "")
    )

    for set_code, set_name in ordered_sets:
        if limit is not None and updated >= limit:
            break
        if set_code not in by_set:
            continue
        if set_code in known_unmatched:
            if set_code not in unmatched_seen:
                unmatched_seen.add(set_code)
                unmatched_sets.append({"set_code": set_code, "set_name": set_name})
            continue
        # Only pull sets that still have missing cards without a successful match.
        missing_n = sum(
            1
            for _n, card in by_set[set_code]
            if str(card.id) not in have_history and card.id not in matched_ids
        )
        if missing_n <= 0:
            continue
        try:
            jset = resolve_set_id(
                set_name,
                set_code=set_code,
                cache=set_cache,
                catalog_rows=catalog_rows,
            )
        except JustTCGRateLimitError:
            print(
                f"JustTCG rate/budget stop pri resolve "
                f"(requests={justtcg_request_count()}).",
                file=sys.stderr,
            )
            return _stats_payload()
        except Exception as exc:
            print(f"  set '{set_name}' resolve fail: {exc}", file=sys.stderr)
            continue
        if not jset:
            print(f"  JustTCG set nije pronađen za '{set_name}' ({set_code})")
            if set_code not in unmatched_seen:
                unmatched_seen.add(set_code)
                unmatched_sets.append({"set_code": set_code, "set_name": set_name})
            continue

        cursor: str | None = None
        print(f"  set {set_name} ({set_code}) → {jset} [fallback]")
        while True:
            try:
                rows, cursor = fetch_set_cards_page(
                    jset, cursor=cursor, limit=JUSTTCG_BATCH_SIZE
                )
            except JustTCGRateLimitError:
                print(
                    f"JustTCG rate/budget stop set sync "
                    f"(requests={justtcg_request_count()}).",
                    file=sys.stderr,
                )
                return _stats_payload()
            except Exception as exc:
                print(f"  page cursor={cursor!r} greška: {exc}", file=sys.stderr)
                break

            if not rows:
                break

            for row in rows:
                card = _match_card(by_set, set_code, str(row.get("number") or ""))
                if card is None:
                    continue
                if str(card.id) in have_history and card.id in matched_ids:
                    continue
                # Prefer filling gaps; skip cards that already have history on fallback.
                if str(card.id) in have_history:
                    continue
                status, written = _ingest_card_row(
                    card,
                    row,
                    have_history=have_history,
                    matched_ids=matched_ids,
                )
                if status == "ok":
                    updated += 1
                    saved += written
                    print(f"  OK {card.id} · set · {written} history pts")
                elif status in {"skip_weak", "skip_empty", "skip_absurd"}:
                    skipped += 1
                if limit is not None and updated >= limit:
                    payload = _stats_payload()
                    print(
                        f"JustTCG limit hit: updated={updated} "
                        f"requests={payload['justtcg_requests']}"
                    )
                    return payload

            if not cursor:
                break

    payload = _stats_payload()
    print(
        f"JustTCG gotovo: updated={updated} batch={batch_updated} skipped={skipped} "
        f"saved_rows={saved} total_history={payload['total_history']} "
        f"requests={payload['justtcg_requests']} "
        f"pkmn_updated={payload['pkmn_updated']} pkmn_attempted={payload['pkmn_attempted']}"
    )
    return payload


def main() -> int:
    print("=== TCG Market: JustTCG NM sync ===")
    try:
        sync_justtcg_price_history()
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Neočekivana greška: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
