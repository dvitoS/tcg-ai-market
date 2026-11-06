"""Sinkronizira NM cijene + history s JustTCG u Supabase (Phase A).

Free tier: paginacija po curated setovima (~50 req/noć, 20/batch, 10/min).
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

from config import JUSTTCG_BATCH_SIZE, catalog_sets
from database import (
    distinct_history_card_ids,
    init_db,
    list_cards,
    replace_card_history,
    table_count,
    update_card_market_price,
)
from justtcg_client import (
    JustTCGRateLimitError,
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
    """Prefer sets with more cards missing price_history (fill gaps first).

    Includes every set present in the DB (full catalog), not only the curated pin list.
    """
    have_history = distinct_history_card_ids()
    scored: list[tuple[int, str, str]] = []
    for set_code, cards in by_set.items():
        missing = sum(1 for _n, card in cards if str(card.id) not in have_history)
        scored.append((missing, set_code, _display_set_name(set_code, cards)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(sid, name) for _m, sid, name in scored]


def sync_justtcg_price_history(*, limit: int | None = None) -> dict[str, int]:
    """Live sync: JustTCG NM + history (JUSTTCG_HISTORY_DURATION) po curated catalog sets."""
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
        }

    updated = skipped = saved = 0
    set_cache: dict[str, str] = {}
    matched_ids: set[str] = set()
    unmatched_sets: list[dict[str, str]] = []
    unmatched_seen: set[str] = set()
    have_history = distinct_history_card_ids()
    ordered_sets = _sets_prioritized_by_coverage(by_set)
    known_unmatched = _known_unmatched_set_codes()
    if known_unmatched:
        print(
            f"Skipping {len(known_unmatched)} previously unmatched JustTCG sets "
            f"(from spot QA snapshot)"
        )

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
        }

    # One catalog fetch — local resolve for every set (avoids ~12s/set search).
    catalog_rows: list | None
    try:
        catalog_rows = list_pokemon_sets()
        print(f"JustTCG pokemon set catalog: {len(catalog_rows)} rows (local resolve)")
    except JustTCGRateLimitError:
        print("JustTCG rate/budget stop pri list_pokemon_sets.", file=sys.stderr)
        return _stats_payload()
    except Exception as exc:
        print(f"JustTCG list_pokemon_sets failed ({exc}) — falling back to per-set q=", file=sys.stderr)
        catalog_rows = None

    print(
        "JustTCG set sync (NM + 30d history) — sets by missing history first: %s"
        % ", ".join(f"{n}({c})" for c, n in ordered_sets)
    )
    # Two passes when limited: fill missing history first, then refresh others.
    passes = (True, False) if limit is not None else (False,)
    for missing_only in passes:
        for set_code, set_name in ordered_sets:
            if set_code not in by_set:
                continue
            if set_code in known_unmatched:
                if set_code not in unmatched_seen:
                    unmatched_seen.add(set_code)
                    unmatched_sets.append(
                        {"set_code": set_code, "set_name": set_name}
                    )
                continue
            if missing_only:
                missing_n = sum(
                    1 for _n, card in by_set[set_code] if str(card.id) not in have_history
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
                    unmatched_sets.append(
                        {"set_code": set_code, "set_name": set_name}
                    )
                continue

            offset = 0
            pass_label = "missing" if missing_only else "refresh"
            print(f"  set {set_name} ({set_code}) → {jset} [{pass_label}]")
            while True:
                try:
                    rows, has_more = fetch_set_cards_page(
                        jset, offset=offset, limit=JUSTTCG_BATCH_SIZE
                    )
                except JustTCGRateLimitError:
                    print(
                        f"JustTCG rate/budget stop set sync "
                        f"(requests={justtcg_request_count()}).",
                        file=sys.stderr,
                    )
                    return _stats_payload()
                except Exception as exc:
                    print(f"  page offset={offset} greška: {exc}", file=sys.stderr)
                    break

                if not rows:
                    break

                for row in rows:
                    card = _match_card(by_set, set_code, str(row.get("number") or ""))
                    if card is None:
                        continue
                    if card.id in matched_ids:
                        continue
                    if missing_only and str(card.id) in have_history:
                        continue

                    variant = pick_nm_variant(list(row.get("variants") or []))
                    points = history_points_from_variant(variant)
                    price = variant_price_usd(variant)
                    tcp = str(row.get("tcgplayerId") or "") or None
                    if not points and price is None:
                        skipped += 1
                        continue

                    if points:
                        # Never wipe a multi-day series with spot-only / tiny payloads.
                        # Soft Ink charts look "broken" when nightly replace leaves 1–2 pts.
                        min_points = 7
                        already = str(card.id) in have_history
                        if len(points) < min_points and already:
                            skipped += 1
                            print(
                                f"  skip weak history {card.id} · {len(points)} pts "
                                f"(keep existing)"
                            )
                        else:
                            written = replace_card_history(card.id, points)
                            saved += written
                            have_history.add(str(card.id))
                    if price is not None:
                        update_card_market_price(card.id, price, tcgplayer_id=tcp)

                    updated += 1
                    matched_ids.add(card.id)
                    print(
                        f"  OK {card.id} · ${price if price is not None else '?'} · {len(points)} pts"
                    )
                    if limit is not None and updated >= limit:
                        payload = _stats_payload()
                        print(
                            f"JustTCG limit hit: updated={updated} "
                            f"requests={payload['justtcg_requests']}"
                        )
                        return payload

                if not has_more:
                    break
                offset += JUSTTCG_BATCH_SIZE

    payload = _stats_payload()
    print(
        f"JustTCG gotovo: updated={updated} skipped={skipped} "
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
