"""Shared card tile HTML for Catalog / Scanner grids."""

from __future__ import annotations

from html import escape

import pandas as pd

from api_client import pokemontcg_image_url
from currency import money
from i18n import signal_label


def card_image_for_id(card_id: str) -> str:
    return pokemontcg_image_url(str(card_id)) or ""


def market_tile_html(row, *, selected: bool = False) -> str:
    """Unified tile for market/scanner/catalog-signals grids."""
    card_id = str(getattr(row, "id", getattr(row, "card_id", "")))
    name = escape(str(getattr(row, "name", getattr(row, "Name", ""))))
    set_name = escape(str(getattr(row, "set_name", getattr(row, "Set", ""))))
    rarity = escape(str(getattr(row, "rarity", getattr(row, "Rarity", "")) or ""))
    signal = str(getattr(row, "signal", "") or "")
    price = getattr(row, "price", None)
    if price is None:
        price = getattr(row, "Current price", 0.0)
    change = getattr(row, "expected_change_pct", None)
    if change is None:
        change = getattr(row, "Expected ROI (%)", None)
    image = escape(card_image_for_id(card_id), quote=True)
    change_txt = f"{float(change):+.1f}%" if change is not None and pd.notna(change) else "—"
    signal_html = (
        f'<span class="market-tile-signal {escape(signal_label(signal))}">{escape(signal_label(signal))}</span>'
        if signal
        else f'<span class="market-tile-meta">{escape(change_txt)}</span>'
    )
    selected_cls = " is-selected" if selected else ""
    return f"""
    <div class="market-tile{selected_cls}">
      <img src="{image}" alt="{name}" loading="lazy"
           onerror="this.style.opacity='0.25';" />
      <div class="market-tile-name">{name}</div>
      <div class="market-tile-meta">{set_name} · {rarity}</div>
      <div class="market-tile-price">{escape(money(float(price)))} · {escape(change_txt)}</div>
      {signal_html}
    </div>
    """


def explore_card_html(row) -> str:
    """Collectr-style explore card."""
    name = escape(str(getattr(row, "name", "")))
    set_name = escape(str(getattr(row, "set_name", "") or ""))
    rarity = escape(str(getattr(row, "rarity", "") or ""))
    price = float(getattr(row, "price", 0.0) or 0.0)
    change = getattr(row, "expected_change_pct", None)
    card_id = str(getattr(row, "id", ""))
    image = escape(card_image_for_id(card_id), quote=True)
    if change is not None and pd.notna(change):
        cls = "up" if float(change) > 0.05 else "down" if float(change) < -0.05 else "flat"
        change_html = f'<div class="explore-card-change {cls}">{float(change):+.1f}%</div>'
    else:
        change_html = '<div class="explore-card-change flat">—</div>'
    meta = " · ".join(p for p in (set_name, rarity) if p)
    return f"""
    <div class="explore-card">
      <img src="{image}" alt="{name}" loading="lazy"
           onerror="this.style.opacity='0.25';" />
      <div class="explore-card-name">{name}</div>
      <div class="explore-card-meta">{meta}</div>
      <div class="explore-card-price">{escape(money(price))}</div>
      {change_html}
    </div>
    """
