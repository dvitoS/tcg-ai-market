"""Backfill cards.tcgplayer_id without burning JustTCG free-tier quota.

Primary path: TCGplayer public search API (set-scoped + number scoring).
Optional: JustTCG via --justtcg (usually 429 on free tier).

  python backfill_tcgplayer_ids.py --limit 40
  python backfill_tcgplayer_ids.py --limit 40 --resume
  python backfill_tcgplayer_ids.py --reset-progress
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import urllib.parse
from typing import Any

import requests

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.backfill_tcp")
PROGRESS_PATH = PROJECT_ROOT / "data" / "backfill_tcgplayer_progress.json"
_TCP_SEARCH_URL = "https://mp-search-api.tcgplayer.com/v1/search/request"
_TCP_HEADERS = {
    "User-Agent": "tcg-ai-market/1.0 (+local backfill)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def _card_number(card_id: str) -> str | None:
    text = str(card_id or "")
    if "-" not in text:
        return None
    return text.rsplit("-", 1)[-1]


def _norm_number(value: str | None) -> str:
    text = str(value or "").strip()
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    return text.lstrip("0") or "0"


def _load_progress() -> set[str]:
    if not PROGRESS_PATH.exists():
        return set()
    try:
        payload = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        return {str(x) for x in (payload.get("done_ids") or [])}
    except Exception:
        return set()


def _save_progress(done_ids: set[str]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps({"done_ids": sorted(done_ids)}, indent=2),
        encoding="utf-8",
    )


def reset_progress() -> None:
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()


def _score_tcp_hit(
    item: dict[str, Any],
    *,
    wanted_name: str,
    wanted_number: str,
    wanted_set: str,
) -> int:
    score = 0
    name = str(item.get("productName") or "").strip().lower()
    set_name = str(item.get("setName") or "").strip().lower()
    attrs = item.get("customAttributes") if isinstance(item.get("customAttributes"), dict) else {}
    number = _norm_number(attrs.get("number") if isinstance(attrs, dict) else None)

    if wanted_number and number == wanted_number:
        score += 100
    elif wanted_number and wanted_number in str(attrs.get("number") or ""):
        score += 40

    if wanted_name and name == wanted_name:
        score += 50
    elif wanted_name and wanted_name in name:
        score += 25

    if wanted_set:
        if set_name == wanted_set:
            score += 40
        elif wanted_set in set_name or set_name in wanted_set:
            score += 25
        else:
            # Soft penalty when set clearly disagrees.
            score -= 10

    # Prefer singles over sealed/lots if name hints at it.
    if "code card" in name or "lot" in name:
        score -= 30
    return score


def _tcp_from_tcgplayer_search(
    *,
    name: str,
    number: str | None,
    set_name: str | None,
) -> str | None:
    """Resolve product id via TCGplayer storefront search (no JustTCG quota)."""
    wanted_name = (name or "").strip()
    if not wanted_name:
        return None
    wanted_number = _norm_number(number) if number else ""
    wanted_set = (set_name or "").strip()

    # Name-only query + set filter works better than "Name 215" (secret rares).
    query = wanted_name
    url = f"{_TCP_SEARCH_URL}?q={urllib.parse.quote(query)}"

    def _search(term: dict[str, list[str]]) -> list[dict[str, Any]]:
        body = {
            "algorithm": "sales_rev_1_labrador",
            "from": 0,
            "size": 12,
            "filters": {"term": term, "range": {}, "match": {}},
            "listingSearch": {
                "context": {"cart": {}},
                "filters": {
                    "term": {"sellerStatus": ["Live"], "channelId": [0]},
                    "range": {"quantity": {"gte": 1}},
                    "exclude": {"channelExclusion": 0},
                },
            },
            "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
            "settings": {"useFuzzySearch": True, "didYouMean": {}},
            "sort": {},
        }
        try:
            response = requests.post(url, json=body, headers=_TCP_HEADERS, timeout=30)
            if response.status_code != 200:
                LOG.debug("tcgplayer search HTTP %s for %r", response.status_code, query)
                return []
            payload = response.json() if response.content else {}
        except Exception as exc:
            LOG.warning("tcgplayer search failed q=%r: %s", query, exc)
            return []
        bucket = (payload.get("results") or [{}])[0]
        items = list(bucket.get("results") or []) if isinstance(bucket, dict) else []
        return [i for i in items if isinstance(i, dict)]

    items: list[dict[str, Any]] = []
    # Prefer set-scoped search when we know the set (Evolving Skies secrets, etc.).
    if wanted_set:
        items = _search({"productLineName": ["pokemon"], "setName": [wanted_set]})
    if not items:
        items = _search({"productLineName": ["pokemon"]})

    best: dict[str, Any] | None = None
    best_score = 0
    for item in items:
        score = _score_tcp_hit(
            item,
            wanted_name=wanted_name.lower(),
            wanted_number=wanted_number,
            wanted_set=wanted_set.lower(),
        )
        if score > best_score:
            best = item
            best_score = score

    # Require a number match when we know the number — avoid wrong secrets/alts.
    if not best or best_score < (100 if wanted_number else 25):
        return None
    raw = best.get("productId")
    if raw is None:
        return None
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        text = str(raw).strip()
        return text if re.fullmatch(r"\d+", text) else None


def backfill_tcgplayer_ids(
    *,
    limit: int | None = None,
    only_missing: bool = True,
    pause_seconds: float | None = None,
    max_consecutive_rate_limits: int = 1,
    resume: bool = False,
    allow_justtcg: bool = False,
) -> dict[str, int]:
    from config import JUSTTCG_REQUEST_DELAY_SECONDS
    from database import (
        cards_have_tcgplayer_id_column,
        get_supabase,
        update_card_tcgplayer_id,
    )
    from justtcg_client import JustTCGRateLimitError, justtcg_api_key, search_pokemon_card

    pause = float(1.25 if pause_seconds is None else pause_seconds)
    justtcg_pause = float(JUSTTCG_REQUEST_DELAY_SECONDS)
    has_justtcg = bool(justtcg_api_key()) and allow_justtcg

    stats = {
        "scanned": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "rate_limited": 0,
        "stopped_early": 0,
        "resumed_skip": 0,
        "from_tcgplayer": 0,
        "from_justtcg": 0,
    }
    if not cards_have_tcgplayer_id_column(force=True):
        LOG.warning("cards.tcgplayer_id column missing — run schema SQL first.")
        return stats

    done = _load_progress() if (resume or PROGRESS_PATH.exists()) else set()
    if done and not resume:
        LOG.info("found progress file with %s ids — continuing from there", len(done))

    client = get_supabase()
    fetch_limit = None if limit is None else max(int(limit) * 5, int(limit) + len(done) + 20)
    query = (
        client.table("cards")
        .select("id,name,set_name,tcgplayer_id")
        .order("market_price", desc=True)
    )
    if fetch_limit is not None:
        query = query.limit(int(fetch_limit))
    rows: list[dict[str, Any]] = list(query.execute().data or [])

    consecutive_429 = 0
    processed_this_run = 0
    for row in rows:
        if limit is not None and processed_this_run >= int(limit):
            break
        if stats["stopped_early"]:
            break

        stats["scanned"] += 1
        card_id = str(row.get("id") or "")
        if card_id in done:
            stats["resumed_skip"] += 1
            continue
        existing = str(row.get("tcgplayer_id") or "").strip()
        if only_missing and existing:
            stats["skipped"] += 1
            done.add(card_id)
            continue

        name = str(row.get("name") or "").strip()
        set_name = str(row.get("set_name") or "").strip() or None
        number = _card_number(card_id)
        processed_this_run += 1

        tcp: str | None = None
        source = ""

        # TCGplayer public search — main free path (pokemontcg rarely has /product/{id} now).
        tcp = _tcp_from_tcgplayer_search(name=name, number=number, set_name=set_name)
        if tcp:
            source = "tcgplayer"
            stats["from_tcgplayer"] += 1
        time.sleep(pause)

        # 3) Optional JustTCG (off by default — free tier is usually 429'd).
        if not tcp and has_justtcg:
            try:
                hit = search_pokemon_card(
                    name=name,
                    number=number,
                    set_name=set_name,
                    quick=True,
                )
                consecutive_429 = 0
                tcp = str((hit or {}).get("tcgplayerId") or "").strip() or None
                if tcp:
                    source = "justtcg"
                    stats["from_justtcg"] += 1
                time.sleep(justtcg_pause)
            except JustTCGRateLimitError:
                stats["rate_limited"] += 1
                consecutive_429 += 1
                wait = min(120.0, max(justtcg_pause * (2**consecutive_429), 45.0))
                LOG.warning(
                    "JustTCG 429 on %s — sleeping %.0fs then stopping",
                    card_id,
                    wait,
                )
                time.sleep(wait)
                processed_this_run -= 1
                stats["stopped_early"] = 1
                _save_progress(done)
                break
            except Exception as exc:
                LOG.warning("JustTCG search failed %s: %s", card_id, exc)
                time.sleep(justtcg_pause)

        if not tcp:
            stats["failed"] += 1
            # Park miss so resume moves on; re-run with --reset-progress to retry.
            done.add(card_id)
            continue
        if tcp == existing:
            stats["skipped"] += 1
            done.add(card_id)
            continue
        try:
            update_card_tcgplayer_id(card_id, tcp)
            stats["updated"] += 1
            done.add(card_id)
            LOG.info("updated %s → %s (%s)", card_id, tcp, source)
        except Exception as exc:
            LOG.warning("update failed %s: %s", card_id, exc)
            stats["failed"] += 1

    _save_progress(done)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Backfill cards.tcgplayer_id")
    parser.add_argument("--limit", type=int, default=25, help="Max cards this run (default 25)")
    parser.add_argument("--pause", type=float, default=None, help="Seconds between TCGplayer searches")
    parser.add_argument("--all", action="store_true", help="Re-resolve even when tcp set")
    parser.add_argument("--resume", action="store_true", help="Skip ids in progress file")
    parser.add_argument(
        "--justtcg",
        action="store_true",
        help="Also try JustTCG when TCGplayer search misses (burns free-tier quota)",
    )
    parser.add_argument("--no-justtcg", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--reset-progress", action="store_true", help="Delete progress file and exit")
    args = parser.parse_args()
    if args.reset_progress:
        reset_progress()
        print(f"cleared {PROGRESS_PATH}")
        return 0
    allow_justtcg = bool(args.justtcg) and not bool(args.no_justtcg)
    stats = backfill_tcgplayer_ids(
        limit=args.limit,
        only_missing=not args.all,
        pause_seconds=args.pause,
        resume=bool(args.resume) or PROGRESS_PATH.exists(),
        allow_justtcg=allow_justtcg,
    )
    print(
        "backfill done "
        f"scanned={stats['scanned']} updated={stats['updated']} "
        f"skipped={stats['skipped']} failed={stats['failed']} "
        f"tcgplayer={stats.get('from_tcgplayer', 0)} "
        f"justtcg={stats.get('from_justtcg', 0)} "
        f"rate_limited={stats['rate_limited']} stopped_early={stats['stopped_early']} "
        f"resumed_skip={stats.get('resumed_skip', 0)}"
    )
    return 0 if stats["updated"] > 0 or stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
