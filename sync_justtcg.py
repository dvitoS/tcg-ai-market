"""Sinkronizira NM cijene + history s JustTCG u Supabase (Phase A).

Free tier: paginacija po curated setovima (~50 req/noć, 20/batch, 10/min).
"""

from __future__ import annotations

import sys
from collections import defaultdict

from config import CATALOG_SETS, JUSTTCG_BATCH_SIZE
from database import (
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


def sync_justtcg_price_history(*, limit: int | None = None) -> dict[str, int]:
    """Live sync: JustTCG NM + 30d history po CATALOG_SETS."""
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

    print("JustTCG set sync (NM + 30d history)...")
    for set_code, set_name in CATALOG_SETS:
        if set_code not in by_set:
            continue
        try:
            jset = resolve_set_id(set_name, cache=set_cache)
        except JustTCGRateLimitError:
            print("JustTCG rate limit pri resolve setova.", file=sys.stderr)
            break
        except Exception as exc:
            print(f"  set '{set_name}' resolve fail: {exc}", file=sys.stderr)
            continue
        if not jset:
            print(f"  JustTCG set nije pronađen za '{set_name}'")
            continue

        offset = 0
        print(f"  set {set_name} ({set_code}) → {jset}")
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

                variant = pick_nm_variant(list(row.get("variants") or []))
                points = history_points_from_variant(variant)
                price = variant_price_usd(variant)
                tcp = str(row.get("tcgplayerId") or "") or None
                if not points and price is None:
                    skipped += 1
                    continue

                if points:
                    written = replace_card_history(card.id, points)
                    saved += written
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
