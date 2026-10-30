"""Backfill cards.tcgplayer_id via ranked JustTCG search (Sprint A).

Run once locally or from nightly (NIGHTLY_BACKFILL_TCP=1):
  python backfill_tcgplayer_ids.py
  python backfill_tcgplayer_ids.py --limit 40
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

LOG = logging.getLogger("tcg.backfill_tcp")


def _card_number(card_id: str) -> str | None:
    text = str(card_id or "")
    if "-" not in text:
        return None
    return text.rsplit("-", 1)[-1]


def backfill_tcgplayer_ids(*, limit: int | None = None, only_missing: bool = True) -> dict[str, int]:
    from database import (
        cards_have_tcgplayer_id_column,
        get_supabase,
        update_card_tcgplayer_id,
    )
    from justtcg_client import justtcg_api_key, search_pokemon_card

    stats = {"scanned": 0, "updated": 0, "skipped": 0, "failed": 0}
    if not justtcg_api_key():
        LOG.warning("JUSTTCG_API_KEY missing — skip tcgplayer_id backfill.")
        return stats
    if not cards_have_tcgplayer_id_column(force=True):
        LOG.warning("cards.tcgplayer_id column missing — run schema SQL first.")
        return stats

    client = get_supabase()
    query = client.table("cards").select("id,name,set_name,tcgplayer_id").order("market_price", desc=True)
    if limit is not None:
        query = query.limit(int(limit))
    rows: list[dict[str, Any]] = list(query.execute().data or [])

    for row in rows:
        stats["scanned"] += 1
        card_id = str(row.get("id") or "")
        existing = str(row.get("tcgplayer_id") or "").strip()
        if only_missing and existing:
            stats["skipped"] += 1
            continue
        name = str(row.get("name") or "").strip()
        set_name = str(row.get("set_name") or "").strip() or None
        number = _card_number(card_id)
        try:
            hit = search_pokemon_card(name=name, number=number, set_name=set_name)
        except Exception as exc:
            LOG.warning("search failed %s: %s", card_id, exc)
            stats["failed"] += 1
            continue
        tcp = str((hit or {}).get("tcgplayerId") or "").strip()
        if not tcp:
            stats["failed"] += 1
            continue
        if tcp == existing:
            stats["skipped"] += 1
            continue
        try:
            update_card_tcgplayer_id(card_id, tcp)
            stats["updated"] += 1
            LOG.info("updated %s → %s", card_id, tcp)
        except Exception as exc:
            LOG.warning("update failed %s: %s", card_id, exc)
            stats["failed"] += 1
        # Be gentle with free-tier rate limits between cards.
        time.sleep(0.2)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Backfill cards.tcgplayer_id from JustTCG")
    parser.add_argument("--limit", type=int, default=None, help="Max cards (price desc)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-resolve even when tcgplayer_id already set",
    )
    args = parser.parse_args()
    stats = backfill_tcgplayer_ids(limit=args.limit, only_missing=not args.all)
    print(
        f"backfill done scanned={stats['scanned']} updated={stats['updated']} "
        f"skipped={stats['skipped']} failed={stats['failed']}"
    )
    return 0 if stats["failed"] == 0 or stats["updated"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
