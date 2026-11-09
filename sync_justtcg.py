"""Sinkronizira NM cijene + history s JustTCG u Supabase (Phase A).

Paid Soft Ink tier: 100 cards/req, 50/min, 1000/day, 10k/month.
Prefer tcgplayer_id batch POSTs (≈1 req / 100 cards) over set pagination.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

from config import JUSTTCG_BATCH_SIZE, catalog_sets
from database import (
    distinct_history_card_ids,
    init_db,
    list_cards,
    list_cards_for_sync,
    replace_card_history,
    table_count,
    update_card_market_price,
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


def sync_justtcg_for_card_ids(
    card_ids: list[str],
    *,
    forbid_spot_keys: set[float] | None = None,
) -> dict[str, int]:
    """Targeted JustTCG batch ingest for an explicit card-id allowlist."""
    if not justtcg_api_key():
        raise RuntimeError("JUSTTCG_API_KEY nije postavljen.")
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
    matched_ids: set[str] = set()
    have_history = distinct_history_card_ids()
    tcp_ids = list(tcp_to_card.keys())
    for i in range(0, len(tcp_ids), JUSTTCG_BATCH_SIZE):
        chunk = tcp_ids[i : i + JUSTTCG_BATCH_SIZE]
        try:
            rows = batch_by_tcgplayer_ids(chunk)
        except JustTCGRateLimitError:
            break
        except Exception as exc:
            print(f"  heal batch offset={i} greška: {exc}", file=sys.stderr)
            continue
        for row in rows:
            tid = card_tcgplayer_id(row) or ""
            card = tcp_to_card.get(tid)
            if card is None:
                continue
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
            elif status == "skip_poison":
                skip_poison += 1
                skipped += 1
            elif status == "skip_absurd":
                skip_absurd += 1
                skipped += 1
            elif status in {"skip_weak", "skip_empty"}:
                skipped += 1
    return {
        "updated": updated,
        "skipped": skipped,
        "saved": saved,
        "skip_poison": skip_poison,
        "skip_absurd": skip_absurd,
        "targeted": len(wanted),
        "with_tcgplayer_id": len(tcp_ids),
        "justtcg_requests": justtcg_request_count(),
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
        f"(of {len(targets)} prioritized, batch={JUSTTCG_BATCH_SIZE})"
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

        for row in rows:
            tid = card_tcgplayer_id(row) or ""
            card = tcp_to_card.get(tid)
            if card is None:
                continue
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
            elif status in {"skip_weak", "skip_empty", "skip_absurd"}:
                skipped += 1
            if limit is not None and updated >= limit:
                payload = _stats_payload()
                print(
                    f"JustTCG limit hit via batch: updated={updated} "
                    f"requests={payload['justtcg_requests']}"
                )
                return payload

    if limit is not None and updated >= limit:
        payload = _stats_payload()
        print(
            f"JustTCG gotovo (batch only): updated={updated} "
            f"requests={payload['justtcg_requests']}"
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
        f"requests={payload['justtcg_requests']}"
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
