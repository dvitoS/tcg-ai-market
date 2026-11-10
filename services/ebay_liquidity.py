"""eBay liquidity snapshots → training / inference features."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from config import _secret

LOG = logging.getLogger("tcg.ebay_liquidity")

TABLE = "ebay_liquidity_snapshots"
EBAY_FEATURE_COLUMNS = (
    "ebay_active_n_log",
    "ebay_ask_premium",
    "ebay_has_obs",
)


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def sample_size() -> int:
    raw = _clean("EBAY_LIQUIDITY_SAMPLE_N") or "40"
    try:
        return max(0, min(200, int(raw)))
    except ValueError:
        return 40


def stats_from_listings(
    listings: list[dict[str, Any]],
    *,
    spot: float | None,
) -> dict[str, float | int | None]:
    prices = sorted(
        float(r["price"])
        for r in listings
        if isinstance(r, dict) and r.get("price") is not None
    )
    n = len(prices)
    ask_min = prices[0] if prices else None
    ask_max = prices[-1] if prices else None
    ask_median = prices[n // 2] if prices else None
    premium = None
    if ask_median is not None and spot is not None and float(spot) > 0:
        premium = float(ask_median) / float(spot) - 1.0
    return {
        "active_n": int(n),
        "ask_min": ask_min,
        "ask_median": ask_median,
        "ask_max": ask_max,
        "spot": float(spot) if spot is not None else None,
        "ask_premium": premium,
    }


def upsert_snapshots(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    try:
        from database import get_supabase

        client = get_supabase()
        # Chunk upserts.
        n = 0
        for i in range(0, len(rows), 80):
            chunk = rows[i : i + 80]
            client.table(TABLE).upsert(chunk, on_conflict="card_id,snapshot_date").execute()
            n += len(chunk)
        return n
    except Exception as exc:
        LOG.warning("ebay_liquidity upsert failed: %s", exc)
        return 0


def load_snapshots(
    *,
    since_date: str | None = None,
) -> pd.DataFrame:
    """Load snapshot history for feature join."""
    try:
        from database import get_supabase

        client = get_supabase()
        query = client.table(TABLE).select(
            "card_id,snapshot_date,active_n,ask_min,ask_median,ask_max,spot,ask_premium"
        )
        if since_date:
            query = query.gte("snapshot_date", str(since_date)[:10])
        response = query.order("snapshot_date").execute()
        data = getattr(response, "data", None) or []
        if not data:
            return pd.DataFrame(
                columns=[
                    "card_id",
                    "snapshot_date",
                    "active_n",
                    "ask_min",
                    "ask_median",
                    "ask_max",
                    "spot",
                    "ask_premium",
                ]
            )
        frame = pd.DataFrame(data)
        frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"]).dt.normalize()
        frame["card_id"] = frame["card_id"].astype(str)
        for col in ("active_n", "ask_min", "ask_median", "ask_max", "spot", "ask_premium"):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame
    except Exception as exc:
        LOG.warning("load ebay_liquidity snapshots failed: %s", exc)
        return pd.DataFrame()


def attach_ebay_features(
    featured: pd.DataFrame,
    snapshots: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """As-of join eBay liquidity onto price history rows (forward-fill within card)."""
    out = featured.copy()
    for col in EBAY_FEATURE_COLUMNS:
        out[col] = 0.0

    snaps = snapshots if snapshots is not None else load_snapshots()
    if snaps is None or snaps.empty or "date" not in out.columns:
        return out

    work = out.copy()
    work["_row"] = np.arange(len(work))
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    work["card_id"] = work["card_id"].astype(str)

    snap = snaps.copy()
    snap["snapshot_date"] = pd.to_datetime(snap["snapshot_date"]).dt.normalize()
    snap = snap.sort_values(["card_id", "snapshot_date"])

    merged_parts: list[pd.DataFrame] = []
    for card_id, group in work.groupby("card_id", sort=False):
        g = group.sort_values("date")
        s = snap.loc[snap["card_id"] == card_id]
        if s.empty:
            part = g.copy()
            part["ebay_active_n"] = np.nan
            part["ebay_ask_premium_raw"] = np.nan
            merged_parts.append(part)
            continue
        joined = pd.merge_asof(
            g,
            s.rename(
                columns={
                    "snapshot_date": "date",
                    "active_n": "ebay_active_n",
                    "ask_premium": "ebay_ask_premium_raw",
                }
            )[["date", "ebay_active_n", "ebay_ask_premium_raw"]],
            on="date",
            direction="backward",
        )
        merged_parts.append(joined)

    merged = pd.concat(merged_parts, ignore_index=True).sort_values("_row")
    has = merged["ebay_active_n"].notna()
    active = pd.to_numeric(merged["ebay_active_n"], errors="coerce").fillna(0.0)
    premium = pd.to_numeric(merged["ebay_ask_premium_raw"], errors="coerce").fillna(0.0)
    # Clip extreme ask premiums from bad matches.
    premium = premium.clip(-0.75, 2.0)
    out["ebay_has_obs"] = has.astype(float).to_numpy()
    out["ebay_active_n_log"] = np.log1p(active.to_numpy(dtype=float))
    out["ebay_ask_premium"] = premium.to_numpy(dtype=float)
    return out


def pick_sample_cards(limit: int) -> pd.DataFrame:
    """Sure-desk tips first, then higher-priced catalog (better eBay hit rate)."""
    if limit <= 0:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(card_id: str, name: str, set_name: str, market_price: Any) -> None:
        cid = str(card_id or "").strip()
        if not cid or cid in seen:
            return
        seen.add(cid)
        rows.append(
            {
                "id": cid,
                "name": name,
                "set_name": set_name,
                "market_price": market_price,
            }
        )

    try:
        from database import get_supabase

        client = get_supabase()
        # Hot desk: conformal BUY/SELL — liquidity features matter most here.
        for signal in ("BUY", "SELL"):
            if len(rows) >= limit:
                break
            need = max(1, limit - len(rows))
            try:
                resp = (
                    client.table("market_quotes")
                    .select("card_id,name,set_name,market_price,expected_change_pct")
                    .eq("signal", signal)
                    .eq("conformal_ok", True)
                    .order(
                        "expected_change_pct",
                        desc=(signal == "BUY"),
                    )
                    .limit(need)
                    .execute()
                )
                for row in list(resp.data or []):
                    _add(
                        row.get("card_id"),
                        str(row.get("name") or ""),
                        str(row.get("set_name") or ""),
                        row.get("market_price"),
                    )
            except Exception as exc:
                LOG.warning("pick_sample sure %s failed: %s", signal, exc)

        if len(rows) < limit:
            response = (
                client.table("cards")
                .select("id,name,set_name,market_price")
                .order("market_price", desc=True)
                .limit(max((limit - len(rows)) * 3, limit))
                .execute()
            )
            for row in list(getattr(response, "data", None) or []):
                if len(rows) >= limit:
                    break
                _add(
                    row.get("id"),
                    str(row.get("name") or ""),
                    str(row.get("set_name") or ""),
                    row.get("market_price"),
                )
    except Exception as exc:
        LOG.warning("pick_sample_cards failed: %s", exc)
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame = frame.dropna(subset=["id", "name"])
    frame["market_price"] = pd.to_numeric(frame.get("market_price"), errors="coerce")
    return frame.head(limit).reset_index(drop=True)


def harvest_ebay_liquidity(
    *,
    limit: int | None = None,
    sleep_s: float = 0.35,
) -> dict[str, Any]:
    """Pull Browse active depth for a sample of cards and upsert today's snapshot."""
    stats = {
        "sampled": 0,
        "upserted": 0,
        "errors": 0,
        "skipped": 0,
        "skip_reason": None,
    }
    try:
        import ebay_client as ebay
    except Exception as exc:
        LOG.warning("ebay_client import failed: %s", exc)
        stats["skipped"] = 1
        stats["skip_reason"] = "import_failed"
        return stats
    if not ebay.ebay_configured():
        LOG.warning(
            "eBay not configured — skip liquidity harvest "
            "(set EBAY_APP_ID + EBAY_CERT_ID in Actions secrets)"
        )
        stats["skipped"] = 1
        stats["skip_reason"] = "ebay_not_configured"
        return stats

    n = int(sample_size() if limit is None else limit)
    if n <= 0:
        LOG.warning("EBAY_LIQUIDITY_SAMPLE_N=%s — harvest disabled", n)
        stats["skipped"] = 1
        stats["skip_reason"] = "sample_n_zero"
        return stats
    cards = pick_sample_cards(n)
    if cards.empty:
        LOG.warning("eBay liquidity harvest: no sample cards")
        stats["skipped"] = 1
        stats["skip_reason"] = "no_sample_cards"
        return stats

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for row in cards.itertuples(index=False):
        stats["sampled"] += 1
        card_id = str(row.id)
        name = str(row.name or "")
        set_name = str(getattr(row, "set_name", "") or "")
        spot = getattr(row, "market_price", None)
        try:
            number = card_id.rsplit("-", 1)[-1] if "-" in card_id else ""
            number = number.lstrip("0") or number
            listings = ebay.listings_for_card(
                name=name,
                set_name=set_name or None,
                number=number or None,
                limit=12,
            )
            st = stats_from_listings(listings, spot=float(spot) if spot == spot else None)
            rows.append(
                {
                    "card_id": card_id,
                    "snapshot_date": today,
                    "active_n": int(st["active_n"] or 0),
                    "ask_min": st["ask_min"],
                    "ask_median": st["ask_median"],
                    "ask_max": st["ask_max"],
                    "spot": st["spot"],
                    "ask_premium": st["ask_premium"],
                    "updated_at": now,
                }
            )
        except Exception as exc:
            stats["errors"] += 1
            LOG.debug("ebay harvest %s failed: %s", card_id, exc)
        if sleep_s > 0:
            time.sleep(sleep_s)

    stats["upserted"] = upsert_snapshots(rows)
    LOG.info("eBay liquidity harvest: %s", stats)
    return stats
