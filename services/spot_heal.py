"""Heal already-poisoned JustTCG spots that quarantine only masks.

Flow:
1. Detect poison-cluster card IDs from the live board (`poison_spot_mask`).
2. Soft-clear ``market_price`` (and optionally history) so ``skip_absurd`` cannot
   block recovery from a prior bad tip.
3. Targeted JustTCG refetch that refuses to rewrite the same poison key.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Literal

import pandas as pd

from services.spot_sanity import _frame_spots, poison_spot_mask

LOG = logging.getLogger("tcg.spot_heal")

HealMode = Literal["dry_run", "null_market", "clear_history", "refetch"]


def poisoned_card_ids_from_board(quotes: pd.DataFrame) -> tuple[list[str], set[float]]:
    """Return (sorted card ids, poison spot keys) for quarantined identical spots."""
    if quotes is None or quotes.empty:
        return [], set()
    mask = poison_spot_mask(quotes)
    if not bool(mask.any()):
        return [], set()
    frame = quotes.loc[mask]
    ids = sorted({str(cid) for cid in frame.get("id", pd.Series(dtype=str)).astype(str).tolist() if str(cid)})
    spots = _frame_spots(frame)
    keys = {float(v) for v in spots.dropna().tolist()}
    return ids, keys


def detect_poisoned_card_ids() -> tuple[list[str], set[float]]:
    from api.catalog_service import load_board

    board, _source = load_board()
    return poisoned_card_ids_from_board(board)


def heal_poisoned_spots(
    *,
    mode: HealMode = "dry_run",
    limit: int | None = None,
    card_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Detect and optionally heal poisoned board spots.

    Modes:
    - dry_run: list only
    - null_market: null ``cards.market_price`` for poisoned IDs
    - clear_history: null market + delete per-card history
    - refetch: null market + clear history + targeted JustTCG sync
    """
    if card_ids is None:
        ids, poison_keys = detect_poisoned_card_ids()
    else:
        ids = sorted({str(cid).strip() for cid in card_ids if str(cid).strip()})
        poison_keys = set()
        if ids:
            # Still derive poison keys from the live board when available.
            try:
                live_ids, poison_keys = detect_poisoned_card_ids()
                if not poison_keys:
                    # Fall back: use current market_price of targeted cards as banned keys.
                    from database import get_card

                    for cid in ids:
                        card = get_card(cid)
                        mp = getattr(card, "market_price", None) if card else None
                        if mp is not None:
                            poison_keys.add(round(float(mp), 2))
                # Keep allowlist intersection informative.
                _ = live_ids
            except Exception as exc:
                LOG.warning("poison key detect failed: %s", exc)

    if limit is not None:
        ids = ids[: max(0, int(limit))]

    out: dict[str, Any] = {
        "mode": mode,
        "ids": ids,
        "count": len(ids),
        "poison_keys": sorted(poison_keys),
        "nulled": 0,
        "history_cleared": 0,
        "updated": 0,
        "skipped": 0,
        "skip_poison": 0,
        "skip_absurd": 0,
        "saved": 0,
    }
    if not ids:
        return out
    if mode == "dry_run":
        return out

    from database import clear_card_market_price, delete_card_history

    for cid in ids:
        clear_card_market_price(cid)
        out["nulled"] += 1
        if mode in {"clear_history", "refetch"}:
            delete_card_history(cid)
            out["history_cleared"] += 1

    if mode != "refetch":
        return out

    from sync_justtcg import sync_justtcg_for_card_ids

    sync = sync_justtcg_for_card_ids(ids, forbid_spot_keys=poison_keys or None)
    out["updated"] = int(sync.get("updated") or 0)
    out["skipped"] = int(sync.get("skipped") or 0)
    out["skip_poison"] = int(sync.get("skip_poison") or 0)
    out["skip_absurd"] = int(sync.get("skip_absurd") or 0)
    out["saved"] = int(sync.get("saved") or 0)
    out["justtcg_requests"] = int(sync.get("justtcg_requests") or 0)
    out["with_tcgplayer_id"] = int(sync.get("with_tcgplayer_id") or 0)
    return out


def nightly_spot_heal_limit() -> int:
    raw = (
        os.environ.get("NIGHTLY_SPOT_HEAL_LIMIT", "").strip()
        or "100"
    )
    try:
        return max(0, int(raw))
    except ValueError:
        return 100


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Heal poisoned JustTCG board spots")
    parser.add_argument(
        "--mode",
        choices=["dry_run", "null_market", "clear_history", "refetch"],
        default="dry_run",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Alias for --mode dry_run")
    args = parser.parse_args(argv)
    mode: HealMode = "dry_run" if args.dry_run else args.mode  # type: ignore[assignment]
    result = heal_poisoned_spots(mode=mode, limit=args.limit)
    print(
        f"spot_heal mode={result['mode']} count={result['count']} "
        f"keys={result['poison_keys']} updated={result.get('updated')} "
        f"skip_poison={result.get('skip_poison')} nulled={result.get('nulled')}"
    )
    if result["ids"][:20]:
        print("ids:", ", ".join(result["ids"][:20]) + ("…" if result["count"] > 20 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
