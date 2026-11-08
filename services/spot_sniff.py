"""Ops spot sniff pack — sample sure Radar rows for manual TCP / eBay checks (M0.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _tcp_product_url(tcgplayer_id: Any) -> str | None:
    tid = str(tcgplayer_id or "").strip()
    if not tid.isdigit():
        return None
    return f"https://www.tcgplayer.com/product/{tid}"


def _kestrel_card_path(card_id: str) -> str:
    from urllib.parse import quote

    return f"/cards/{quote(str(card_id), safe='')}"


def build_spot_sniff_pack(*, limit: int = 20) -> dict[str, Any]:
    """Return a balanced sample of sure UNDER/OVER rows for manual sniffing.

    Marketing spend must not launch until an ops human marks this pack as
    passing against TCGplayer market + eBay sold comps.
    """
    limit = max(4, min(int(limit or 20), 40))
    half = max(2, limit // 2)

    from api.radar_service import build_radar

    radar = build_radar(min_edge=0, limit=half, share_safe=True)
    under = list(radar.get("underpriced") or [])[:half]
    over = list(radar.get("overpriced") or [])[:half]

    items: list[dict[str, Any]] = []
    for side, rows in (("UNDER", under), ("OVER", over)):
        for row in rows:
            card_id = str(row.get("id") or "").strip()
            if not card_id:
                continue
            tcp = row.get("tcgplayer_id")
            items.append(
                {
                    "card_id": card_id,
                    "name": str(row.get("name") or card_id),
                    "set_name": row.get("set_name"),
                    "rarity": row.get("rarity"),
                    "side": side,
                    "spot": row.get("spot") if row.get("spot") is not None else row.get("price"),
                    "fair_price": row.get("fair_price")
                    if row.get("fair_price") is not None
                    else row.get("predicted_price"),
                    "edge_pct": row.get("edge_pct"),
                    "tcgplayer_id": str(tcp) if tcp is not None else None,
                    "tcgplayer_url": _tcp_product_url(tcp),
                    "kestrel_path": _kestrel_card_path(card_id),
                    "check_tcp": None,
                    "check_ebay": None,
                    "notes": "",
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limit": limit,
        "count": len(items),
        "under_n": sum(1 for i in items if i["side"] == "UNDER"),
        "over_n": sum(1 for i in items if i["side"] == "OVER"),
        "board_source": str(radar.get("source") or "empty"),
        "pass_required": True,
        "instructions": (
            "For each row: open TCGplayer market and recent eBay sold comps. "
            "Mark pass only if spot is plausible for NM and the sure side still makes sense. "
            "Any hard fail → block marketing spend (G0)."
        ),
        "items": items,
    }
