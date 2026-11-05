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
    normalize_card_number,
    pick_nm_variant,
    resolve_set_id,
    variant_price_usd,
)


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
        return {"updated": 0, "skipped": 0, "saved": 0, "total_history": 0}

    updated = skipped = saved = 0
    set_cache: dict[str, str] = {}
    matched_ids: set[str] = set()
    have_history = distinct_history_card_ids()
    ordered_sets = _sets_prioritized_by_coverage(by_set)

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
            try:
                jset = resolve_set_id(
                    set_name, set_code=set_code, cache=set_cache
                )
            except JustTCGRateLimitError:
                print("JustTCG rate limit pri resolve setova.", file=sys.stderr)
                total = table_count("price_history")
                return {
                    "updated": updated,
                    "skipped": skipped,
                    "saved": saved,
                    "total_history": int(total),
                }
            except Exception as exc:
                print(f"  set '{set_name}' resolve fail: {exc}", file=sys.stderr)
                continue
            if not jset:
                print(f"  JustTCG set nije pronađen za '{set_name}'")
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
                    print("JustTCG rate limit — stop set sync.", file=sys.stderr)
                    total = table_count("price_history")
                    return {
                        "updated": updated,
                        "skipped": skipped,
                        "saved": saved,
                        "total_history": int(total),
                    }
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
                        total = table_count("price_history")
                        return {
                            "updated": updated,
                            "skipped": skipped,
                            "saved": saved,
                            "total_history": int(total),
                        }

                if not has_more:
                    break
                offset += JUSTTCG_BATCH_SIZE

    total = table_count("price_history")
    print(
        f"JustTCG gotovo: updated={updated} skipped={skipped} "
        f"saved_rows={saved} total_history={total}"
    )
    return {
        "updated": updated,
        "skipped": skipped,
        "saved": saved,
        "total_history": int(total),
    }


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
