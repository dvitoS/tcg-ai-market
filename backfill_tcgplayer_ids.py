"""Backfill cards.tcgplayer_id via ranked JustTCG search (Sprint A).

Rate-limit friendly: one quick search per card, pause between cards, stop on 429 streak.

  python backfill_tcgplayer_ids.py --limit 10
  python backfill_tcgplayer_ids.py --limit 40 --pause 8
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


def backfill_tcgplayer_ids(
    *,
    limit: int | None = None,
    only_missing: bool = True,
    pause_seconds: float | None = None,
    max_consecutive_rate_limits: int = 3,
) -> dict[str, int]:
    from config import JUSTTCG_REQUEST_DELAY_SECONDS
    from database import (
        cards_have_tcgplayer_id_column,
        get_supabase,
        update_card_tcgplayer_id,
    )
    from justtcg_client import JustTCGRateLimitError, justtcg_api_key, search_pokemon_card

    pause = float(JUSTTCG_REQUEST_DELAY_SECONDS if pause_seconds is None else pause_seconds)
    stats = {
        "scanned": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "rate_limited": 0,
        "stopped_early": 0,
    }
    if not justtcg_api_key():
        LOG.warning("JUSTTCG_API_KEY missing — skip tcgplayer_id backfill.")
        return stats
    if not cards_have_tcgplayer_id_column(force=True):
        LOG.warning("cards.tcgplayer_id column missing — run schema SQL first.")
        return stats

    client = get_supabase()
    query = (
        client.table("cards")
        .select("id,name,set_name,tcgplayer_id")
        .order("market_price", desc=True)
    )
    if limit is not None:
        query = query.limit(int(limit))
    rows: list[dict[str, Any]] = list(query.execute().data or [])

    consecutive_429 = 0
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
            # Quick = name+number only — fewer API calls under free-tier limits.
            hit = search_pokemon_card(
                name=name,
                number=number,
                set_name=set_name,
                quick=True,
            )
            consecutive_429 = 0
        except JustTCGRateLimitError:
            stats["rate_limited"] += 1
            consecutive_429 += 1
            LOG.warning(
                "rate limited on %s (%s/%s) — backing off %.0fs",
                card_id,
                consecutive_429,
                max_consecutive_rate_limits,
                pause * 2,
            )
            time.sleep(max(pause * 2, 12.0))
            if consecutive_429 >= max_consecutive_rate_limits:
                stats["stopped_early"] = 1
                LOG.warning("stopping backfill after repeated 429s — retry later")
                break
            continue
        except Exception as exc:
            LOG.warning("search failed %s: %s", card_id, exc)
            stats["failed"] += 1
            time.sleep(pause)
            continue

        tcp = str((hit or {}).get("tcgplayerId") or "").strip()
        if not tcp:
            stats["failed"] += 1
            time.sleep(pause)
            continue
        if tcp == existing:
            stats["skipped"] += 1
            time.sleep(pause)
            continue
        try:
            update_card_tcgplayer_id(card_id, tcp)
            stats["updated"] += 1
            LOG.info("updated %s → %s", card_id, tcp)
        except Exception as exc:
            LOG.warning("update failed %s: %s", card_id, exc)
            stats["failed"] += 1
        time.sleep(pause)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Backfill cards.tcgplayer_id from JustTCG")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max cards by market_price desc (default 10)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=None,
        help="Seconds between cards (default JUSTTCG_REQUEST_DELAY_SECONDS)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-resolve even when tcgplayer_id already set",
    )
    args = parser.parse_args()
    stats = backfill_tcgplayer_ids(
        limit=args.limit,
        only_missing=not args.all,
        pause_seconds=args.pause,
    )
    print(
        "backfill done "
        f"scanned={stats['scanned']} updated={stats['updated']} "
        f"skipped={stats['skipped']} failed={stats['failed']} "
        f"rate_limited={stats['rate_limited']} stopped_early={stats['stopped_early']}"
    )
    if stats.get("stopped_early"):
        return 2
    return 0 if stats["failed"] == 0 or stats["updated"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
