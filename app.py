"""TCG AI Market Dashboard — stvarna povijest cijena i XGBoost."""

import importlib
import subprocess
import sys

_REQUIRED_PIP = ("plotly", "xgboost", "scikit-learn")


def _ensure_runtime_deps() -> None:
    """Streamlit Cloud ponekad ne povuče requirements.txt — instaliraj kritične pakete."""
    missing: list[str] = []
    for name in _REQUIRED_PIP:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if not missing:
        return
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", *_REQUIRED_PIP],
    )
    importlib.invalidate_caches()


_ensure_runtime_deps()

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from ai_xgboost import (
    FEATURE_COLUMNS,
    add_time_features,
    card_forecasts,
    drop_incomplete_rows,
    load_history,
    resample_daily_history,
    split_features,
    train_xgboost,
)
from api_client import pokemontcg_image_url
from database import (
    add_portfolio_position,
    delete_portfolio_position,
    ensure_seed_database,
    init_db,
    load_portfolio_lots as fetch_portfolio_lots,
)
from generate_history import ensure_price_history
from currency import (
    currency_code,
    currency_symbol,
    from_display,
    money,
    money_delta,
    money_signed,
    number_format_pattern,
    to_display,
)
from i18n import (
    FILTER_ALL,
    FILTER_ALL_SETS,
    PNL_ALL,
    PNL_DOWN,
    PNL_TOP,
    PNL_UP,
    signal_label,
    t,
)

st.set_page_config(
    page_title="TCG AI Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Promjena unutar ovog pojasa ostaje DRŽI; izvan njega je KUPI ili PRODAJ.
HOLD_BAND = 0.0035
FORECAST_DAYS = 7
SCANNER_GROWTH_FLOOR = 10.0
MARKET_PAGE_SIZE_DEFAULT = 24
SIGNAL_CLASS = {"KUPI": "signal-buy", "PRODAJ": "signal-sell", "DRŽI": "signal-hold"}
HOLO_RARITY_KEYWORDS = ("rare", "holo", "secret", "ultra")

CUSTOM_CSS = """
<style>
    .stApp { background: radial-gradient(circle at top left, #132238 0%, #0b1220 45%, #070b14 100%); }
    h1, h2, h3, p, label, span, div { color: #e8eef8 !important; }
    [data-testid="stSidebar"] { background: #0d1626; border-right: 1px solid #1f334d; }
    [data-testid="stMetric"] {
        background: #132033;
        border: 1px solid #24364d;
        border-radius: 14px;
        padding: 12px 16px;
    }
    .signal-buy, .signal-sell, .signal-hold {
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-align: center;
        padding: 18px;
        border-radius: 14px;
    }
    .signal-pct {
        margin-top: 6px;
        font-size: 1.05rem;
        letter-spacing: 0.04em;
        font-weight: 650;
    }
    .signal-buy {
        background: linear-gradient(90deg, #14532d, #166534);
        border: 1px solid #22c55e;
        color: #dcfce7 !important;
    }
    .signal-sell {
        background: linear-gradient(90deg, #7f1d1d, #991b1b);
        border: 1px solid #f87171;
        color: #fee2e2 !important;
    }
    .signal-hold {
        background: linear-gradient(90deg, #78350f, #92400e);
        border: 1px solid #fbbf24;
        color: #fef3c7 !important;
    }
    .detail-row, .stat-row {
        display: grid;
        gap: 12px;
        margin-bottom: 8px;
    }
    .detail-row { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .stat-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .chip {
        background: #132033;
        border: 1px solid #24364d;
        border-radius: 14px;
        padding: 12px 16px;
        min-width: 0;
    }
    .chip-label { font-size: 0.8rem; opacity: 0.72; margin-bottom: 4px; }
    .chip-value { font-size: 1.05rem; font-weight: 650; line-height: 1.3; }
    .chip-value.pnl-up { color: #4ade80 !important; }
    .chip-value.pnl-down { color: #f87171 !important; }
    .ai-outlook {
        border-radius: 14px;
        padding: 16px 18px;
        margin: 4px 0 16px;
        font-size: 1.05rem;
        font-weight: 650;
        line-height: 1.45;
    }
    .ai-outlook.up { background: #14532d; border: 1px solid #22c55e; }
    .ai-outlook.down { background: #7f1d1d; border: 1px solid #f87171; }
    .ai-outlook.flat { background: #1e293b; border: 1px solid #64748b; }
    .scanner-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin: 18px 0 8px;
    }
    .market-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 18px 16px;
        margin: 8px 0 12px;
    }
    .market-tile {
        text-align: center;
        padding: 6px 4px 8px;
        margin: 0;
        border-radius: 10px;
        border: 2px solid transparent;
        transition: border-color 0.15s ease, background 0.15s ease;
    }
    .market-tile.is-selected {
        border-color: #38bdf8;
        background: rgba(56, 189, 248, 0.08);
    }
    .market-tile img {
        display: block;
        width: 100%;
        height: auto;
        border-radius: 4.35% / 3%;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    }
    .market-tile-name {
        margin: 8px 0 2px;
        font-size: 0.86rem;
        font-weight: 700;
        line-height: 1.25;
        color: #f8fafc !important;
    }
    .market-tile-meta {
        font-size: 0.72rem;
        opacity: 0.78;
        color: #94a3b8 !important;
        margin: 0 0 4px;
    }
    .market-tile-price {
        font-size: 0.92rem;
        font-weight: 650;
        color: #e2e8f0 !important;
        margin: 0;
    }
    .market-tile-signal {
        display: inline-block;
        margin-top: 6px;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
    }
    .market-tile-signal.KUPI { background: #14532d; border: 1px solid #22c55e; color: #dcfce7 !important; }
    .market-tile-signal.PRODAJ { background: #7f1d1d; border: 1px solid #f87171; color: #fee2e2 !important; }
    .market-tile-signal.DRZI, .market-tile-signal.DRŽI { background: #78350f; border: 1px solid #fbbf24; color: #fef3c7 !important; }
    div[data-testid="stHorizontalBlock"]:has(button[kind="primary"][key="lang_hr_btn"]),
    div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"][key="lang_hr_btn"]) {
        justify-content: flex-end;
    }
    .pager-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin: 4px 0 14px;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 30px;
        margin: 4px 0 12px;
        padding: 0;
    }
    /* Perspective kartica — stil blizak tcg.pokemon.com galleries */
    /* Okvir prati točno dimenzije slike karte (bez praznog ruba). */
    .pokemon-card {
        background: transparent;
        border: none;
        border-radius: 0;
        text-align: center;
        padding: 0;
        width: 100%;
        margin: 0 auto;
        overflow: visible;
    }
    .pokemon-card-stage {
        perspective: 1000px;
        margin: 0;
        width: 100%;
        line-height: 0;
        cursor: pointer;
        touch-action: none;
        overflow: visible;
    }
    .pokemon-card-transformer {
        position: relative;
        display: block;
        width: 100%;
        transform-style: preserve-3d;
        will-change: transform;
        transition: transform 0.12s ease-out;
        border-radius: 4.35% / 3%;
        line-height: 0;
        overflow: visible;
    }
    .pokemon-card-art {
        display: block;
        width: 100% !important;
        max-width: none !important;
        height: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        border-radius: 4.35% / 3%;
        background: transparent;
        box-shadow: 0 5px 5px rgba(0, 0, 0, 0);
        transition: box-shadow 0.45s linear;
        backface-visibility: hidden;
        vertical-align: top;
    }
    .pokemon-card.is-over .pokemon-card-art {
        box-shadow: 5px 5px 20px rgba(0, 0, 0, 0.45);
    }
    .pokemon-card-shine {
        pointer-events: none;
        position: absolute;
        inset: 0;
        border-radius: 4.35% / 3%;
        overflow: hidden;
        mix-blend-mode: color-dodge;
        opacity: 0;
        transition: opacity 0.2s ease;
        transform: translateZ(1px);
    }
    .pokemon-card.is-over .pokemon-card-shine { opacity: 0.85; }
    /* Holo-foil overlay samo preko art-a (transformer), ne preko Količina/Profit teksta */
    .holo-card .pokemon-card-transformer::after {
        content: "";
        pointer-events: none;
        position: absolute;
        inset: 0;
        border-radius: 4.35% / 3%;
        z-index: 2;
        background: linear-gradient(
            125deg,
            rgba(255, 255, 255, 0) 0%,
            rgba(0, 255, 255, 0.3) 30%,
            rgba(255, 0, 255, 0.3) 50%,
            rgba(255, 255, 0, 0.3) 70%,
            rgba(255, 255, 255, 0) 100%
        );
        background-size: 250% 250%;
        background-position: 100% 50%;
        mix-blend-mode: color-dodge;
        opacity: 0;
        transition: opacity 0.4s ease, background-position 0.4s ease;
        transform: translateZ(2px);
    }
    .holo-card:hover .pokemon-card-transformer::after,
    .holo-card.is-over .pokemon-card-transformer::after {
        opacity: 0.8;
        background-position: 0% 50%;
    }
    .pokemon-card-labels {
        position: relative;
        z-index: 1;
        isolation: isolate;
        margin-top: 0;
    }
    .pokemon-card-name {
        font-size: 0.9rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 8px 0 3px;
        color: #f8fafc !important;
    }
    .pokemon-card-meta {
        font-size: 0.78rem;
        opacity: 0.85;
        margin: 0 0 2px;
        color: #cbd5e1 !important;
    }
    .pokemon-card-value {
        font-size: 0.9rem;
        font-weight: 650;
        margin: 2px 0;
        color: #e2e8f0 !important;
    }
    .pokemon-card-pnl { margin: 2px 0 0; }
    .pokemon-card-pnl.up { color: #4ade80 !important; font-weight: 700; }
    .pokemon-card-pnl.down { color: #f87171 !important; font-weight: 700; }
    .pokemon-card-pnl.flat { color: #94a3b8 !important; font-weight: 650; }
    .gallery-slot {
        --card-w: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        width: var(--card-w);
        max-width: 100%;
        margin: 0 auto;
    }
    div[data-testid="stMarkdown"]:has(.gallery-slot),
    div[data-testid="stMarkdown"]:has(.gallery-slot) > div,
    div[data-testid="stMarkdownContainer"]:has(.gallery-slot) {
        padding: 0 !important;
        margin: 0 !important;
        width: fit-content !important;
        max-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.gallery-slot) {
        gap: 30px !important;
        column-gap: 30px !important;
    }
    div[data-testid="stColumn"]:has(.gallery-slot) {
        flex: 0 0 auto !important;
        width: auto !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    .gallery-slot div[data-testid="stButton"] button {
        width: 100%;
        background: transparent !important;
        border: 1px solid #334155 !important;
        color: #94a3b8 !important;
        border-radius: 10px !important;
        padding: 0.2rem 0.4rem !important;
        min-height: 2rem;
    }
    .gallery-slot div[data-testid="stButton"] button:hover {
        border-color: #f87171 !important;
        color: #fecaca !important;
    }
    /* Lightbox (klik na kartu) — isti 3D hover kao u galeriji */
    #tcg-card-lightbox {
        position: fixed;
        inset: 0;
        z-index: 99999;
        display: none;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.62);
        backdrop-filter: blur(6px);
        padding: 24px;
        opacity: 0;
        transition: opacity 0.35s ease;
    }
    #tcg-card-lightbox.is-open {
        display: flex;
        opacity: 1;
    }
    #tcg-card-lightbox .tcg-lb-panel {
        position: relative;
        width: min(360px, 86vw);
        text-align: center;
        opacity: 0;
        transform: scale(0.92) translateY(14px);
        transition: opacity 0.35s ease, transform 0.4s ease;
    }
    #tcg-card-lightbox.is-open .tcg-lb-panel {
        opacity: 1;
        transform: scale(1) translateY(0);
    }
    #tcg-card-lightbox .tcg-lb-stage {
        perspective: 1200px;
        width: 100%;
        line-height: 0;
        cursor: grab;
        touch-action: none;
        overflow: visible;
    }
    #tcg-card-lightbox .tcg-lb-transformer {
        position: relative;
        display: block;
        width: 100%;
        transform-style: preserve-3d;
        will-change: transform;
        transition: transform 0.12s ease-out;
        line-height: 0;
        overflow: visible;
    }
    #tcg-card-lightbox .tcg-lb-transformer.is-tilting {
        transition: none;
    }
    #tcg-card-lightbox img.tcg-lb-art {
        width: 100%;
        height: auto;
        border-radius: 4.35% / 3%;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5);
        display: block;
        transition: box-shadow 0.35s ease;
        backface-visibility: hidden;
    }
    #tcg-card-lightbox .tcg-lb-stage.is-over img.tcg-lb-art {
        box-shadow: 8px 12px 36px rgba(0, 0, 0, 0.55);
    }
    #tcg-card-lightbox .tcg-lb-shine {
        pointer-events: none;
        position: absolute;
        inset: 0;
        border-radius: 4.35% / 3%;
        overflow: hidden;
        mix-blend-mode: color-dodge;
        opacity: 0;
        transition: opacity 0.2s ease;
        transform: translateZ(1px);
    }
    #tcg-card-lightbox .tcg-lb-stage.is-over .tcg-lb-shine {
        opacity: 0.9;
    }
    #tcg-card-lightbox .tcg-lb-caption {
        margin-top: 14px;
        text-align: center;
        color: #f8fafc !important;
        font-weight: 650;
        font-size: 1.05rem;
    }
    #tcg-card-lightbox .tcg-lb-close {
        position: fixed;
        top: 1rem;
        right: 1rem;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.25);
        background: rgba(255, 255, 255, 0.12);
        color: #fff !important;
        cursor: pointer;
        backdrop-filter: blur(8px);
        font-size: 1.1rem;
        line-height: 1;
    }
    @media (prefers-reduced-motion: reduce) {
        .pokemon-card-transformer, #tcg-card-lightbox, #tcg-card-lightbox .tcg-lb-panel {
            transition: none !important;
        }
    }
    @media (max-width: 1100px) {
        .detail-row, .stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    /* ——— Collectr-style desktop navbar ——— */
    .nav-brand-left {
        font-family: Georgia, "Times New Roman", Times, serif;
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.2em;
        color: #fafafa !important;
        line-height: 1.05;
        padding: 0;
        text-transform: uppercase;
        user-select: none;
        white-space: nowrap;
    }
    .nav-brand-left span {
        display: block;
        font-family: Lato, "Segoe UI", system-ui, sans-serif;
        font-size: 0.48rem;
        font-weight: 600;
        letter-spacing: 0.28em;
        text-transform: uppercase;
        color: #a1a1aa !important;
        margin-top: 3px;
    }
    /* Single sticky row — Collectr header */
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) {
        position: sticky !important;
        top: 0 !important;
        z-index: 1000 !important;
        gap: 0.25rem !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        min-height: 3.75rem;
        max-height: 4.5rem;
        padding: 0.35rem 0.15rem;
        margin: 0 0 0.75rem;
        background: rgba(10, 10, 10, 0.92) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        > div[data-testid="stColumn"] {
        flex: 1 1 0 !important;
        min-width: 0 !important;
    }
    /* Ghost text links (not pills) */
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) button {
        border-radius: 8px !important;
        font-family: Lato, "Segoe UI", system-ui, sans-serif !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        letter-spacing: 0 !important;
        padding: 0.45rem 0.55rem !important;
        min-height: 2.25rem !important;
        height: 2.25rem !important;
        line-height: 1 !important;
        border: none !important;
        background: transparent !important;
        color: rgba(250, 250, 250, 0.78) !important;
        box-shadow: none !important;
        transition: color 0.15s ease, background 0.15s ease !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) button p {
        font-size: inherit !important;
        font-weight: inherit !important;
        color: inherit !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) button:hover {
        background: rgba(255, 255, 255, 0.06) !important;
        color: #fafafa !important;
        border: none !important;
        box-shadow: none !important;
        transform: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        button[kind="primary"],
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        button[data-testid="baseButton-primary"] {
        background: transparent !important;
        border: none !important;
        color: #2dd4bf !important;
        box-shadow: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        button[kind="primary"]:hover,
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        button[data-testid="baseButton-primary"]:hover {
        background: rgba(45, 212, 191, 0.08) !important;
        color: #5eead4 !important;
        box-shadow: none !important;
    }
    /* Compact lang + currency on the right */
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        > div[data-testid="stColumn"]:nth-last-child(-n + 3) button {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.04em !important;
        padding: 0.3rem 0.45rem !important;
        min-height: 1.85rem !important;
        height: 1.85rem !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        background: transparent !important;
        color: rgba(250, 250, 250, 0.85) !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        > div[data-testid="stColumn"]:nth-last-child(-n + 3)
        button[kind="primary"],
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        > div[data-testid="stColumn"]:nth-last-child(-n + 3)
        button[data-testid="baseButton-primary"] {
        border-color: rgba(45, 212, 191, 0.45) !important;
        color: #5eead4 !important;
        background: rgba(45, 212, 191, 0.08) !important;
    }
    header[data-testid="stHeader"],
    header.stAppHeader {
        background: rgba(10, 10, 10, 0.85) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-bottom: none !important;
    }
    div[data-testid="stDecoration"] {
        display: none !important;
    }
    .stMainBlockContainer.block-container,
    .block-container {
        padding-top: 0.5rem !important;
    }
    .explore-search-wrap {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 14px;
        padding: 18px 20px 14px;
        margin: 6px 0 14px;
    }
    .explore-search-wrap h3 {
        margin: 0 0 10px !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
    }
    .explore-filter-panel {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 14px;
        padding: 14px 14px 8px;
        margin-top: 4px;
    }
    .explore-filter-panel h4 {
        margin: 0 0 10px !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
    }
    .explore-filter-label {
        font-size: 0.78rem;
        font-weight: 650;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #94a3b8 !important;
        margin: 12px 0 6px;
    }
    .explore-card {
        background: rgba(26, 26, 26, 0.18);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 13px 10px 14px;
        text-align: center;
        height: 100%;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        transition: border-color 0.15s ease, transform 0.15s ease, background 0.15s ease;
        pointer-events: none;
    }
    .explore-card img {
        display: block;
        width: 72%;
        max-width: 140px;
        margin: 0 auto 10px;
        height: auto;
        border-radius: 4.35% / 3%;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
    }
    .explore-card-name {
        font-size: 0.8rem;
        font-weight: 700;
        color: #f8fafc !important;
        line-height: 1.3;
        margin: 0 0 4px;
        min-height: 2.4em;
    }
    .explore-card-meta {
        font-size: 0.65rem;
        color: #94a3b8 !important;
        margin: 0 0 9px;
        line-height: 1.35;
    }
    .explore-card-price {
        font-size: 0.93rem;
        font-weight: 700;
        color: #f8fafc !important;
        margin: 0;
    }
    .explore-card-change {
        font-size: 0.7rem;
        font-weight: 650;
        margin-top: 4px;
    }
    .explore-card-change.up { color: #4ade80 !important; }
    .explore-card-change.down { color: #f87171 !important; }
    .explore-card-change.flat { color: #94a3b8 !important; }
    div[data-testid="stColumn"]:has(.explore-card):hover .explore-card {
        border-color: rgba(255, 255, 255, 0.14);
        background: rgba(26, 26, 26, 0.28);
        transform: translateY(-2px);
    }
    .explore-sort-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 4px 0 12px;
        font-size: 0.9rem;
        color: #cbd5e1 !important;
    }

    /* AI detail — desktop: slika lijevo, ime/cijena desno (bez overflowa) */
    .detail-hero {
        display: grid;
        grid-template-columns: 110px minmax(0, 1fr);
        gap: 14px;
        align-items: start;
        background: rgba(16, 24, 40, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 14px;
        margin: 0 0 12px;
        overflow: hidden;
    }
    .detail-hero img {
        display: block;
        width: 110px;
        max-width: 110px;
        height: auto;
        margin: 0;
        border-radius: 4.35% / 3%;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        object-fit: contain;
    }
    .detail-hero-copy {
        min-width: 0;
        overflow-wrap: anywhere;
    }
    .detail-hero-title {
        font-size: 1.2rem;
        font-weight: 800;
        color: #f8fafc !important;
        margin: 0 0 6px;
        line-height: 1.25;
        text-align: left;
    }
    .detail-hero-meta {
        color: #94a3b8 !important;
        font-size: 0.8rem;
        margin: 0 0 10px;
        text-align: left;
        line-height: 1.35;
    }
    .detail-hero-price {
        font-size: 1.45rem;
        font-weight: 800;
        color: #f8fafc !important;
        margin: 0;
        text-align: left;
    }
    .detail-hero-delta {
        text-align: left;
        margin-top: 4px;
        font-size: 0.88rem;
    }
    .detail-hero-delta.up { color: #4ade80 !important; font-weight: 700; }
    .detail-hero-delta.down { color: #f87171 !important; font-weight: 700; }
    .detail-hero-delta.flat { color: #94a3b8 !important; font-weight: 700; }
    .detail-ai-head {
        background: rgba(16, 24, 40, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 16px;
        padding: 14px 16px;
        margin: 0 0 8px;
        text-align: center;
    }
    .detail-ai-head h3 {
        margin: 0 !important;
        font-size: 1.05rem !important;
        color: #f8fafc !important;
        text-align: center;
        line-height: 1.3;
    }
    .compare-head {
        background: rgba(16, 24, 40, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 16px;
        padding: 16px 20px;
        margin: 0 0 8px;
        text-align: center;
    }
    .compare-head h3 {
        margin: 0 0 6px !important;
        font-size: 1.25rem !important;
        color: #f8fafc !important;
        line-height: 1.3;
        text-align: center;
    }
    .compare-head .compare-caption {
        color: #94a3b8 !important;
        font-size: 0.85rem;
        margin: 0;
        line-height: 1.45;
        text-align: center;
    }
    .source-card {
        background: rgba(10, 14, 24, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 12px 14px;
        margin-top: 10px;
    }
    .source-card .src-title {
        font-weight: 700;
        color: #e2e8f0 !important;
        margin: 0 0 4px;
    }
    .source-card .src-meta {
        color: #94a3b8 !important;
        font-size: 0.8rem;
        margin: 0;
    }
    .source-card .src-price {
        font-size: 1.35rem;
        font-weight: 800;
        color: #f8fafc !important;
        margin: 8px 0 0;
    }
</style>
"""

EXPLORE_BATCH = 24

EXPLORE_INFINITE_SCROLL_JS = """
(function () {
  const doc = window.parent.document;
  if (doc.documentElement.dataset.exploreScrollBound === "1") return;
  doc.documentElement.dataset.exploreScrollBound = "1";
  let busy = false;
  function loadMoreLabel(text) {
    const t = (text || "").trim().toLowerCase();
    return t.includes("load more") || t.includes("učitaj još") || t.includes("ucitaj jos");
  }
  function nearBottom() {
    const el = doc.scrollingElement || doc.documentElement;
    return el.scrollTop + window.parent.innerHeight > el.scrollHeight - 520;
  }
  function tryClick() {
    if (busy || !nearBottom()) return;
    const buttons = Array.from(doc.querySelectorAll("button"));
    const btn = buttons.find((b) => loadMoreLabel(b.innerText) && !b.disabled);
    if (!btn) return;
    busy = true;
    btn.click();
    setTimeout(function () { busy = false; }, 900);
  }
  window.parent.addEventListener("scroll", function () {
    clearTimeout(window.parent.__exploreScrollT);
    window.parent.__exploreScrollT = setTimeout(tryClick, 180);
  }, true);
})();
"""

# Overlay + sakrij Streamlit gumb preko cijele Explore kartice (radi na Cloud).
EXPLORE_CARD_HIT_JS = """
(function () {
  const doc = window.parent.document;
  function styleHitTargets() {
    doc.querySelectorAll('[data-testid="stColumn"]').forEach(function (col) {
      const card = col.querySelector('.explore-card');
      if (!card) return;
      const wrap = col.querySelector('[data-testid="stButton"], div.stButton');
      if (!wrap) return;
      const btn = wrap.querySelector('button');
      if (!btn) return;
      const h = Math.max(card.offsetHeight || 0, 200);
      wrap.style.marginTop = (-h) + 'px';
      wrap.style.marginBottom = '0.4rem';
      wrap.style.height = h + 'px';
      wrap.style.position = 'relative';
      wrap.style.zIndex = '6';
      wrap.style.overflow = 'hidden';
      btn.style.opacity = '0';
      btn.style.background = 'transparent';
      btn.style.border = 'none';
      btn.style.boxShadow = 'none';
      btn.style.width = '100%';
      btn.style.height = h + 'px';
      btn.style.minHeight = h + 'px';
      btn.style.padding = '0';
      btn.style.cursor = 'pointer';
      btn.setAttribute('aria-label', 'Open card');
      btn.querySelectorAll('p, span, div').forEach(function (el) {
        el.style.display = 'none';
      });
    });
  }
  styleHitTargets();
  clearTimeout(window.parent.__exploreHitT);
  window.parent.__exploreHitT = setTimeout(styleHitTargets, 120);
  setTimeout(styleHitTargets, 400);
  if (!window.parent.__exploreHitObs) {
    window.parent.__exploreHitObs = new MutationObserver(function () {
      clearTimeout(window.parent.__exploreHitT);
      window.parent.__exploreHitT = setTimeout(styleHitTargets, 80);
    });
    window.parent.__exploreHitObs.observe(doc.body, { childList: true, subtree: true });
  }
})();
"""


def trading_signal(current_price: float, predicted_price: float) -> str:
    change = (predicted_price - current_price) / current_price
    if change > HOLD_BAND:
        return "KUPI"
    if change < -HOLD_BAND:
        return "PRODAJ"
    return "DRŽI"


def assign_signals(quotes: pd.DataFrame) -> pd.DataFrame:
    board = quotes.copy()
    board["expected_change_pct"] = (board["predicted_price"] - board["price"]) / board["price"] * 100.0
    board["signal"] = [
        trading_signal(float(current), float(predicted))
        for current, predicted in zip(board["price"], board["predicted_price"], strict=True)
    ]
    return board


@st.cache_resource(show_spinner="Učitavam povijest i treniram XGBoost...")
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    init_db()
    if ensure_seed_database():
        # Seed napuni praznu Cloud bazu (tcg_market.db je u .gitignore).
        pass
    else:
        # Lokalni fallback: sintetička povijest ako postoje karte bez history redova.
        ensure_price_history()
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    quotes = assign_signals(card_forecasts(model, featured))
    return history, quotes.sort_values("name").reset_index(drop=True), model


def card_history(history: pd.DataFrame, card_id: str) -> pd.DataFrame:
    """Isti dnevni resampling kao u treningu: mean po danu, zatim ffill."""
    raw = history.loc[history["card_id"] == card_id].sort_values("date")
    if raw.empty:
        return raw.reset_index(drop=True)
    return resample_daily_history(raw.copy()).reset_index(drop=True)


def lag_features_for_last_day(series: pd.DataFrame) -> dict[str, float] | None:
    """Lag 1/3/7 i 7-dnevni prosjek na zadnjem danu očišćenog niza."""
    prices = series.sort_values("date")["price"].astype(float).reset_index(drop=True)
    if len(prices) < 8:
        return None
    return {
        "price_lag_1": float(prices.iloc[-2]),
        "price_lag_3": float(prices.iloc[-4]),
        "price_lag_7": float(prices.iloc[-8]),
        "rolling_mean_7": float(prices.iloc[-7:].mean()),
    }


def predict_from_prices(model, prices, rarity_encoded: float, supertype_encoded: float) -> float | None:
    """Jedan korak unaprijed iz zadnjih cijena. Lagovi su isti kao u treningu."""
    values = pd.Series(prices, dtype=float).reset_index(drop=True)
    if len(values) < 8:
        return None
    row = {
        "price_lag_1": float(values.iloc[-2]),
        "price_lag_3": float(values.iloc[-4]),
        "price_lag_7": float(values.iloc[-8]),
        "rolling_mean_7": float(values.iloc[-7:].mean()),
        "rarity_encoded": float(rarity_encoded),
        "supertype_encoded": float(supertype_encoded),
    }
    features = pd.DataFrame([row])[FEATURE_COLUMNS]
    return float(model.predict(features)[0])


def predict_next_close(model, series: pd.DataFrame, rarity_encoded: float, supertype_encoded: float) -> float | None:
    prices = series.sort_values("date")["price"]
    return predict_from_prices(model, prices, rarity_encoded, supertype_encoded)


def forecast_price_in_days(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
    days: int = FORECAST_DAYS,
) -> float | None:
    """Sedam uzastopnih dnevnih prognoza: svaki korak ulazi u lagove sljedećeg."""
    prices = series.sort_values("date")["price"].astype(float).tolist()
    for _ in range(days):
        nxt = predict_from_prices(model, prices, rarity_encoded, supertype_encoded)
        if nxt is None:
            return None
        prices.append(max(nxt, 0.0))
    return prices[-1]


def price_chart(
    series: pd.DataFrame,
    predicted: float | None,
    name: str,
    *,
    source_label: str | None = None,
    show_ai: bool = True,
    line_color: str = "#38bdf8",
) -> go.Figure:
    if series.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title=name,
            height=360,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.65)",
            annotations=[
                dict(
                    text=t("source_unavailable"),
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(color="#94a3b8", size=14),
                )
            ],
        )
        return fig

    last_day = pd.Timestamp(series["date"].iloc[-1])
    last_price = float(series["price"].iloc[-1])
    y_hist = series["price"].astype(float).map(to_display)
    close_label = source_label or t("chart_close")
    money_hover = f"{currency_symbol()}%{{y:.4f}}"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=series["date"],
            y=y_hist,
            mode="lines",
            name=close_label,
            line=dict(color=line_color, width=2.4),
            hovertemplate=f"%{{x|%d.%m.%Y}}<br>{money_hover}<extra>{close_label}</extra>",
        )
    )

    y_values = [float(y_hist.min()), float(y_hist.max())]
    if show_ai and predicted is not None:
        next_day = last_day + pd.Timedelta(days=1)
        y_last = to_display(last_price)
        y_pred = to_display(predicted)
        signal = trading_signal(last_price, predicted)
        forecast_color = {"KUPI": "#22c55e", "PRODAJ": "#f87171", "DRŽI": "#fbbf24"}[signal]
        ai_label = t("chart_ai")
        fig.add_trace(
            go.Scatter(
                x=[last_day, next_day],
                y=[y_last, y_pred],
                mode="lines+markers",
                name=ai_label,
                line=dict(color=forecast_color, width=2.5, dash="dash"),
                marker=dict(size=9, symbol="diamond", color=forecast_color),
                hovertemplate=f"%{{x|%d.%m.%Y}}<br>{money_hover}<extra>AI</extra>",
            )
        )
        y_values.extend([y_last, y_pred])

    price_low = min(y_values)
    price_high = max(y_values)
    pad = max((price_high - price_low) * 0.18, abs(price_low) * 0.01, 0.01)
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=t("xaxis_date"),
        yaxis_title=t("yaxis_price", code=currency_code()),
        height=420,
        margin=dict(l=16, r=16, t=24, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,18,32,0.65)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor="#1e293b",
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor="#1e293b",
            showgrid=True,
            tickprefix=currency_symbol(),
            range=[price_low - pad, price_high + pad],
        ),
    )
    return fig


def chip_row(items: list[tuple[str, str]], css_class: str) -> None:
    cells = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value">{escape(value)}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="{css_class}">{cells}</div>', unsafe_allow_html=True)


def is_holo_eligible(rarity: str | None, *, is_top_ai: bool = False) -> bool:
    """Rijetke / holo karte i TOP AI prilike dobivaju holo-foil klasu."""
    if is_top_ai:
        return True
    text = str(rarity or "").lower()
    return any(keyword in text for keyword in HOLO_RARITY_KEYWORDS)


def load_portfolio_lots() -> pd.DataFrame:
    lots = fetch_portfolio_lots()
    if lots.empty:
        return lots
    lots["image_url"] = [
        (url if isinstance(url, str) and url.strip() else pokemontcg_image_url(str(card_id)))
        for url, card_id in zip(lots["image_url"], lots["card_id"], strict=True)
    ]
    return lots


def hires_card_image(url: str | None) -> str:
    """Za lightbox koristi _hires varijantu s images.pokemontcg.io ako postoji."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "images.pokemontcg.io" in raw and raw.endswith(".png") and "_hires" not in raw:
        return raw[:-4] + "_hires.png"
    return raw


def portfolio_card_html(row) -> str:
    """Jedna kartica galerije: 3D stage + sjaj + oznake."""
    pnl = float(row.pnl)
    pnl_pct = float(row.pnl_pct)
    tone = "up" if pnl > 0 else "down" if pnl < 0 else "flat"
    image = escape(str(getattr(row, "image_url", None) or ""), quote=True)
    full = escape(hires_card_image(getattr(row, "image_url", None)), quote=True)
    name = escape(str(row.name))
    is_top_ai = bool(getattr(row, "is_top_ai", False))
    rarity = getattr(row, "rarity", None)
    holo_class = " holo-card" if is_holo_eligible(rarity, is_top_ai=is_top_ai) else ""
    qty_txt = escape(t("qty_label", n=int(row.quantity)))
    click_title = escape(t("click_zoom"), quote=True)
    img_alt_fail = escape(t("image_unavailable"), quote=True)
    return f"""
    <div class="pokemon-card{holo_class}" data-full-src="{full}" data-card-name="{name}">
      <div class="pokemon-card-stage" title="{click_title}">
        <div class="pokemon-card-transformer">
          <img class="pokemon-card-art" src="{image}" alt="{name}" loading="lazy"
               onerror="this.style.opacity='0.25'; this.alt='{img_alt_fail}';" />
          <div class="pokemon-card-shine" aria-hidden="true"></div>
        </div>
      </div>
      <div class="pokemon-card-labels">
        <div class="pokemon-card-name">{name}</div>
        <div class="pokemon-card-meta">{qty_txt}</div>
        <div class="pokemon-card-value">{escape(money(float(row.market_value)))}</div>
        <div class="pokemon-card-pnl {tone}">{escape(money_signed(pnl))} / {pnl_pct:+.1f}%</div>
      </div>
    </div>
    """


POKEMON_CARD_FX_JS = r"""
(function () {
  const doc = window.parent.document;
  const reduceMotion = window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureLightbox() {
    let box = doc.getElementById('tcg-card-lightbox');
    if (box) return box;
    box = doc.createElement('div');
    box.id = 'tcg-card-lightbox';
    box.innerHTML = `
      <button type="button" class="tcg-lb-close" aria-label="Zatvori">✕</button>
      <div class="tcg-lb-panel">
        <div class="tcg-lb-stage">
          <div class="tcg-lb-transformer">
            <img class="tcg-lb-art" alt="" />
            <div class="tcg-lb-shine" aria-hidden="true"></div>
          </div>
        </div>
        <div class="tcg-lb-caption"></div>
      </div>`;
    doc.body.appendChild(box);

    const stage = box.querySelector('.tcg-lb-stage');
    const transformer = box.querySelector('.tcg-lb-transformer');
    const shine = box.querySelector('.tcg-lb-shine');

    const resetTilt = () => {
      stage.classList.remove('is-over');
      transformer.classList.remove('is-tilting');
      transformer.style.transform = 'rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
      shine.style.background = '';
      shine.style.opacity = '';
    };

    stage.addEventListener('mousemove', (e) => {
      if (!box.classList.contains('is-open')) return;
      if (reduceMotion) {
        stage.classList.add('is-over');
        transformer.style.transform = 'translateY(-8px) scale3d(1.04, 1.04, 1.04)';
        return;
      }
      const r = stage.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      const rotY = (x - 0.5) * 40;
      const rotX = (0.5 - y) * 28;
      transformer.classList.add('is-tilting');
      transformer.style.transform =
        `rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.08, 1.08, 1.08)`;
      shine.style.opacity = '0.95';
      shine.style.background =
        `radial-gradient(circle at ${x * 100}% ${y * 100}%, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.14) 28%, transparent 55%)`;
      stage.classList.add('is-over');
    });
    stage.addEventListener('mouseleave', resetTilt);

    const close = () => {
      resetTilt();
      box.classList.remove('is-open');
      setTimeout(() => { if (!box.classList.contains('is-open')) box.style.display = 'none'; }, 350);
    };
    box.querySelector('.tcg-lb-close').addEventListener('click', close);
    box.addEventListener('click', (e) => { if (e.target === box) close(); });
    doc.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && box.classList.contains('is-open')) close();
    });
    return box;
  }

  function openLightbox(card) {
    let box = ensureLightbox();
    // Ako je lightbox već postojao sa starim HTML-om, zamijeni ga novom strukturom.
    if (!box.querySelector('.tcg-lb-stage')) {
      box.remove();
      box = ensureLightbox();
    }
    const img = box.querySelector('img.tcg-lb-art');
    const caption = box.querySelector('.tcg-lb-caption');
    const transformer = box.querySelector('.tcg-lb-transformer');
    const stage = box.querySelector('.tcg-lb-stage');
    const shine = box.querySelector('.tcg-lb-shine');
    const src = card.getAttribute('data-full-src') || card.querySelector('img')?.src || '';
    const name = card.getAttribute('data-card-name') || '';
    img.src = src;
    img.alt = name;
    caption.textContent = name;
    stage.classList.remove('is-over');
    transformer.style.transform = 'rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
    shine.style.background = '';
    shine.style.opacity = '';
    box.style.display = 'flex';
    requestAnimationFrame(() => box.classList.add('is-open'));
  }

  function enhance(card) {
    if (card.dataset.enhanced === '1') return;
    card.dataset.enhanced = '1';
    const stage = card.querySelector('.pokemon-card-stage');
    const transformer = card.querySelector('.pokemon-card-transformer');
    const shine = card.querySelector('.pokemon-card-shine');
    if (!stage || !transformer) return;

    const reset = () => {
      card.classList.remove('is-over');
      transformer.style.transform = 'rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
      if (shine) {
        shine.style.background = '';
        shine.style.opacity = '';
      }
    };

    stage.addEventListener('mousemove', (e) => {
      if (reduceMotion) {
        card.classList.add('is-over');
        transformer.style.transform = 'translateY(-6px) scale3d(1.04, 1.04, 1.04)';
        return;
      }
      const r = stage.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      const rotY = (x - 0.5) * 36;
      const rotX = (0.5 - y) * 26;
      transformer.style.transform =
        `rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.07, 1.07, 1.07)`;
      if (shine) {
        shine.style.opacity = '0.9';
        shine.style.background =
          `radial-gradient(circle at ${x * 100}% ${y * 100}%, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0.12) 28%, transparent 55%)`;
      }
      card.classList.add('is-over');
    });
    stage.addEventListener('mouseleave', reset);
    stage.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openLightbox(card);
    });
  }

  function scan() {
    doc.querySelectorAll('.pokemon-card').forEach(enhance);
  }

  scan();
  setTimeout(scan, 150);
  setTimeout(scan, 500);
  if (!window.parent.__tcgCardFxObserver) {
    const observer = new MutationObserver(() => scan());
    observer.observe(doc.body, { childList: true, subtree: true });
    window.parent.__tcgCardFxObserver = observer;
  }
})();
"""


def inject_pokemon_card_fx() -> None:
    """3D tilt + shine + lightbox u parent Streamlit dokumentu (kao službena galerija)."""
    # height>0 da Streamlit iframe pouzdano izvrši skriptu nakon reruna.
    components.html(
        f"<script>{POKEMON_CARD_FX_JS}</script>",
        height=1,
        width=1,
    )


def price_bounds(series: pd.Series, *, fallback_hi: float = 100.0) -> tuple[float, float]:
    """Zaokruženi min/max za slider; jamči lo < hi."""
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0, float(fallback_hi)
    lo = float(np.floor(values.min() * 100) / 100)
    hi = float(np.ceil(values.max() * 100) / 100)
    if hi <= lo:
        hi = lo + 1.0
    return max(0.0, lo), hi


def render_price_slider(key: str, series: pd.Series) -> tuple[float, float]:
    """Uski slider (~33%) + ručni min/max. Vraća (min, max) u USD."""
    lo_usd, hi_usd = price_bounds(series)
    bound_lo = float(to_display(lo_usd))
    bound_hi = float(to_display(hi_usd))
    if bound_hi <= bound_lo:
        bound_hi = bound_lo + 1.0
    span = bound_hi - bound_lo
    step = 0.01 if span <= 20 else 0.5 if span <= 200 else 1.0

    range_key = f"{key}_slider"
    lo_key = f"{key}_lo"
    hi_key = f"{key}_hi"

    def _clamp_pair(low: float, high: float) -> tuple[float, float]:
        low = min(max(float(low), bound_lo), bound_hi)
        high = min(max(float(high), bound_lo), bound_hi)
        if low > high:
            low, high = high, low
        return low, high

    if range_key not in st.session_state:
        st.session_state[range_key] = (bound_lo, bound_hi)
    low, high = _clamp_pair(*st.session_state[range_key])
    st.session_state[range_key] = (low, high)
    # Number inputs prate isti raspon (postavi prije widgeta).
    st.session_state[lo_key] = low
    st.session_state[hi_key] = high

    def _sync_from_slider() -> None:
        pair = st.session_state[range_key]
        low_v, high_v = _clamp_pair(pair[0], pair[1])
        st.session_state[range_key] = (low_v, high_v)
        st.session_state[lo_key] = low_v
        st.session_state[hi_key] = high_v

    def _sync_from_min() -> None:
        low_v, high_v = _clamp_pair(st.session_state[lo_key], st.session_state[hi_key])
        if low_v > high_v:
            high_v = low_v
        st.session_state[range_key] = (low_v, high_v)
        st.session_state[lo_key] = low_v
        st.session_state[hi_key] = high_v

    def _sync_from_max() -> None:
        low_v, high_v = _clamp_pair(st.session_state[lo_key], st.session_state[hi_key])
        if high_v < low_v:
            low_v = high_v
        st.session_state[range_key] = (low_v, high_v)
        st.session_state[lo_key] = low_v
        st.session_state[hi_key] = high_v

    st.caption(t("price_range", code=currency_code()))
    # ~33% + min + max (+ praznina)
    c_slider, c_min, c_max, _ = st.columns([2, 1, 1, 2])
    with c_slider:
        st.slider(
            t("price_range", code=currency_code()),
            min_value=bound_lo,
            max_value=bound_hi,
            step=float(step),
            format=number_format_pattern(digits=2),
            key=range_key,
            label_visibility="collapsed",
            on_change=_sync_from_slider,
        )
    with c_min:
        st.number_input(
            t("price_min"),
            min_value=bound_lo,
            max_value=bound_hi,
            step=float(step),
            format="%.2f",
            key=lo_key,
            on_change=_sync_from_min,
        )
    with c_max:
        st.number_input(
            t("price_max"),
            min_value=bound_lo,
            max_value=bound_hi,
            step=float(step),
            format="%.2f",
            key=hi_key,
            on_change=_sync_from_max,
        )

    low, high = st.session_state[range_key]
    return from_display(float(low)), from_display(float(high))


def apply_price_range(
    frame: pd.DataFrame,
    column: str,
    price_min: float,
    price_max: float,
) -> pd.DataFrame:
    if column not in frame.columns or frame.empty:
        return frame
    prices = pd.to_numeric(frame[column], errors="coerce")
    return frame.loc[prices.between(price_min, price_max, inclusive="both")].copy()


def filter_portfolio_gallery(
    view: pd.DataFrame,
    *,
    query: str,
    rarity: str,
    pnl_filter: str,
    sort_by: str,
    price_min: float | None = None,
    price_max: float | None = None,
) -> pd.DataFrame:
    frame = view.copy()
    if query.strip():
        q = query.strip()
        name_ok = frame["name"].astype(str).str.contains(q, case=False, na=False)
        id_ok = frame["card_id"].astype(str).str.contains(q, case=False, na=False)
        frame = frame.loc[name_ok | id_ok]
    if rarity != FILTER_ALL and "rarity" in frame.columns:
        frame = frame.loc[frame["rarity"].astype(str) == rarity]
    if pnl_filter == PNL_UP:
        frame = frame.loc[frame["pnl"] > 0]
    elif pnl_filter == PNL_DOWN:
        frame = frame.loc[frame["pnl"] < 0]
    elif pnl_filter == PNL_TOP:
        if "is_top_ai" in frame.columns:
            frame = frame.loc[frame["is_top_ai"].astype(bool)]
    if price_min is not None and price_max is not None:
        frame = apply_price_range(frame, "current_price", price_min, price_max)

    sort_map = {
        "name": ("name", True),
        "value_desc": ("market_value", False),
        "value_asc": ("market_value", True),
        "pnl_desc": ("pnl", False),
        "pnl_asc": ("pnl", True),
        "qty_desc": ("quantity", False),
    }
    column, ascending = sort_map.get(sort_by, ("name", True))
    if column in frame.columns:
        frame = frame.sort_values(column, ascending=ascending, kind="mergesort")
    return frame.reset_index(drop=True)


def render_portfolio_gallery(view: pd.DataFrame) -> None:
    """Vizualna galerija inspirirana tcg.pokemon.com galleries."""
    st.markdown(f"##### {t('gallery_title')}")
    st.caption(t("gallery_caption"))

    rarities = [FILTER_ALL]
    if "rarity" in view.columns:
        rarities += sorted({str(r) for r in view["rarity"].dropna().unique().tolist() if str(r).strip()})

    f1, f2, f3, f4 = st.columns([1.6, 1.1, 1, 1.2])
    query = f1.text_input(t("search"), placeholder=t("search_ph"), key="gallery_query")
    rarity_filter = f2.selectbox(
        t("rarity"),
        rarities,
        format_func=lambda r: t("all") if r == FILTER_ALL else r,
        key="gallery_rarity",
    )
    pnl_options = [PNL_ALL, PNL_UP, PNL_DOWN, PNL_TOP]
    pnl_labels = {
        PNL_ALL: t("pnl_all"),
        PNL_UP: t("pnl_up"),
        PNL_DOWN: t("pnl_down"),
        PNL_TOP: t("pnl_top_ai"),
    }
    pnl_filter = f3.selectbox(
        t("pnl"),
        pnl_options,
        format_func=lambda k: pnl_labels[k],
        key="gallery_pnl",
    )
    sort_options = ["name", "value_desc", "value_asc", "pnl_desc", "pnl_asc", "qty_desc"]
    sort_labels = {
        "name": t("sort_name"),
        "value_desc": t("sort_value_desc"),
        "value_asc": t("sort_value_asc"),
        "pnl_desc": t("sort_pnl_desc"),
        "pnl_asc": t("sort_pnl_asc"),
        "qty_desc": t("sort_qty_desc"),
    }
    sort_by = f4.selectbox(
        t("sort"),
        sort_options,
        format_func=lambda k: sort_labels[k],
        key="gallery_sort",
    )
    price_col = "current_price" if "current_price" in view.columns else "market_value"
    price_min, price_max = render_price_slider("gallery_price", view[price_col])

    filtered = filter_portfolio_gallery(
        view,
        query=query,
        rarity=rarity_filter,
        pnl_filter=pnl_filter,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max,
    )
    st.caption(t("shown_of", n=len(filtered), total=len(view)))

    if filtered.empty:
        st.info(t("no_entries_filters"))
        inject_pokemon_card_fx()
        return

    st.markdown('<div class="card-grid">', unsafe_allow_html=True)
    cols_per_row = 4
    rows = list(filtered.itertuples(index=False))
    for start in range(0, len(rows), cols_per_row):
        chunk = rows[start : start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, row in zip(cols, chunk, strict=False):
            entry_id = int(row.id)
            with col:
                st.markdown(
                    f'<div class="gallery-slot">{portfolio_card_html(row)}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("❌", key=f"del_{entry_id}", help=t("remove", name=row.name)):
                    if delete_portfolio_position(entry_id):
                        st.session_state["portfolio_notice"] = t(
                            "removed_from_portfolio", name=row.name
                        )
                    else:
                        st.session_state["portfolio_notice"] = t("entry_not_found", id=entry_id)
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    inject_pokemon_card_fx()

def portfolio_view(lots: pd.DataFrame, market: pd.DataFrame, history: pd.DataFrame, model) -> pd.DataFrame:
    """Spaja nabave sa zadnjim zatvaranjem i 7-dnevnom prognozom."""
    quote_cols = ["id", "price", "rarity_encoded", "supertype_encoded"]
    if "rarity" in market.columns and "rarity" not in lots.columns:
        quote_cols.append("rarity")
    quotes = market[quote_cols].rename(columns={"id": "card_id"})
    view = lots.merge(quotes, on="card_id", how="left", suffixes=("", "_mkt"))
    if "rarity_mkt" in view.columns:
        view["rarity"] = view["rarity"].fillna(view["rarity_mkt"])
        view = view.drop(columns=["rarity_mkt"])
    view["current_price"] = view["price"].fillna(view["market_price"]).astype(float)
    view["invested"] = view["quantity"] * view["purchase_price"]
    view["market_value"] = view["quantity"] * view["current_price"]
    view["pnl"] = view["market_value"] - view["invested"]
    view["pnl_pct"] = np.where(view["invested"] > 0, view["pnl"] / view["invested"] * 100.0, 0.0)

    week_prices: list[float] = []
    for lot in view.itertuples(index=False):
        series = card_history(history, str(lot.card_id))
        if series.empty or pd.isna(lot.rarity_encoded):
            week_prices.append(float(lot.current_price))
            continue
        forecast = forecast_price_in_days(
            model,
            series,
            float(lot.rarity_encoded),
            float(lot.supertype_encoded),
        )
        week_prices.append(float(forecast) if forecast is not None else float(lot.current_price))
    view["week_price"] = week_prices
    view["week_value"] = view["quantity"] * view["week_price"]
    # Isti prag kao AI Scanner TOP prilike — te karte također dobivaju holo-foil.
    view["week_roi_pct"] = np.where(
        view["current_price"] > 0,
        (view["week_price"] - view["current_price"]) / view["current_price"] * 100.0,
        0.0,
    )
    view["is_top_ai"] = view["week_roi_pct"] >= SCANNER_GROWTH_FLOOR
    return view


def render_portfolio_kpis(value: float, invested: float, pnl: float, pnl_pct: float) -> None:
    tone = "pnl-up" if pnl > 0 else "pnl-down" if pnl < 0 else ""
    pnl_text = f"{money_signed(pnl)} / {pnl_pct:+.1f}%"
    cells = [
        (t("kpi_value"), money(value), ""),
        (t("kpi_invested"), money(invested), ""),
        (t("kpi_pnl"), pnl_text, tone),
    ]
    html = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value {css}">{escape(text)}</div></div>'
        for label, text, css in cells
    )
    st.markdown(f'<div class="stat-row">{html}</div>', unsafe_allow_html=True)


def render_week_outlook(current_value: float, week_value: float) -> None:
    if current_value <= 0:
        return
    change_pct = (week_value - current_value) / current_value * 100.0
    if change_pct > 0.05:
        tone = "up"
        sentence = t("outlook_up", pct=change_pct)
    elif change_pct < -0.05:
        tone = "down"
        sentence = t("outlook_down", pct=abs(change_pct))
    else:
        tone = "flat"
        sentence = t("outlook_flat")
    st.markdown(f'<div class="ai-outlook {tone}">{escape(sentence)}</div>', unsafe_allow_html=True)
    st.caption(
        t(
            "outlook_caption",
            current=money(current_value),
            week=money(week_value),
            days=FORECAST_DAYS,
        )
    )

def card_image_for_id(card_id: str) -> str:
    return pokemontcg_image_url(str(card_id)) or ""


def market_tile_html(row, *, selected: bool = False) -> str:
    """Jedan tile u market/scanner gridu."""
    card_id = str(getattr(row, "id", getattr(row, "card_id", "")))
    name = escape(str(getattr(row, "name", getattr(row, "Naziv", ""))))
    set_name = escape(str(getattr(row, "set_name", getattr(row, "Set", ""))))
    rarity = escape(str(getattr(row, "rarity", getattr(row, "Rijetkost", "")) or ""))
    signal = str(getattr(row, "signal", "") or "")
    price = getattr(row, "price", None)
    if price is None:
        price = getattr(row, "Trenutna cijena", 0.0)
    change = getattr(row, "expected_change_pct", None)
    if change is None:
        change = getattr(row, "Očekivani ROI (%)", None)
    image = escape(card_image_for_id(card_id), quote=True)
    change_txt = f"{float(change):+.1f}%" if change is not None and pd.notna(change) else "—"
    css_signal = "DRZI" if signal == "DRŽI" else signal
    signal_html = (
        f'<span class="market-tile-signal {escape(css_signal)}">{escape(signal_label(signal))}</span>'
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


def filter_market_frame(
    market: pd.DataFrame,
    *,
    query: str,
    set_name: str,
    rarity: str,
    signal: str,
    sort_by: str,
    price_min: float | None = None,
    price_max: float | None = None,
) -> pd.DataFrame:
    frame = market.copy()
    if query.strip():
        q = query.strip()
        mask = frame["name"].astype(str).str.contains(q, case=False, na=False) | frame[
            "id"
        ].astype(str).str.contains(q, case=False, na=False)
        frame = frame.loc[mask]
    if set_name != FILTER_ALL_SETS:
        frame = frame.loc[frame["set_name"] == set_name]
    if rarity != FILTER_ALL:
        frame = frame.loc[frame["rarity"] == rarity]
    if signal != FILTER_ALL and "signal" in frame.columns:
        frame = frame.loc[frame["signal"] == signal]
    if price_min is not None and price_max is not None:
        frame = apply_price_range(frame, "price", price_min, price_max)

    sort_map = {
        "name": ("name", True),
        "price_desc": ("price", False),
        "price_asc": ("price", True),
        "exp_desc": ("expected_change_pct", False),
        "exp_asc": ("expected_change_pct", True),
    }
    column, ascending = sort_map.get(sort_by, ("name", True))
    if column in frame.columns:
        frame = frame.sort_values(column, ascending=ascending, kind="mergesort")
    return frame.reset_index(drop=True)


def paginate_frame(frame: pd.DataFrame, page: int, page_size: int) -> tuple[pd.DataFrame, int, int]:
    total = len(frame)
    pages = max(1, (total + page_size - 1) // page_size) if page_size else 1
    page = min(max(1, page), pages)
    start = (page - 1) * page_size
    return frame.iloc[start : start + page_size].copy(), page, pages


def render_pager(prefix: str, page: int, pages: int, total: int, page_size: int) -> int:
    """Prev/next + info. Vraća novi broj stranice."""
    start = (page - 1) * page_size + 1 if total else 0
    end = min(page * page_size, total)
    left, mid, right = st.columns([1, 2, 1])
    with left:
        if st.button(t("prev"), key=f"{prefix}_prev", disabled=page <= 1):
            page = max(1, page - 1)
            st.session_state[f"{prefix}_page"] = page
            st.rerun()
    with mid:
        st.markdown(
            f'<div class="pager-bar" style="justify-content:center;">'
            f"{t('page_of', page=page, pages=pages, start=start, end=end, total=total)}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button(t("next"), key=f"{prefix}_next", disabled=page >= pages):
            page = min(pages, page + 1)
            st.session_state[f"{prefix}_page"] = page
            st.rerun()
    return int(st.session_state.get(f"{prefix}_page", page))


def render_market_grid(
    page_rows: pd.DataFrame,
    cols_per_row: int = 6,
    *,
    selection_key: str | None = None,
) -> None:
    rows = list(page_rows.itertuples(index=False))
    if not rows:
        st.info(t("no_cards_display"))
        return
    selected_id = str(st.session_state.get(selection_key) or "") if selection_key else ""
    for start in range(0, len(rows), cols_per_row):
        chunk = rows[start : start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, row in zip(cols, chunk, strict=False):
            with col:
                card_id = str(getattr(row, "id", getattr(row, "card_id", "")))
                is_selected = bool(selection_key) and card_id == selected_id
                st.markdown(market_tile_html(row, selected=is_selected), unsafe_allow_html=True)
                if selection_key:
                    if st.button(
                        t("show_ai"),
                        key=f"{selection_key}_pick_{card_id}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                        help=t("click_card_ai"),
                    ):
                        st.session_state[selection_key] = card_id
                        st.rerun()


def render_pill_toggle(options: list[tuple[str, str]], *, state_key: str, default: str) -> str:
    """Segmentirani gumbi (TCG Forecast stil). options: [(value, label), ...]."""
    if state_key not in st.session_state:
        st.session_state[state_key] = default
    current = st.session_state[state_key]
    cols = st.columns(len(options))
    for col, (value, label) in zip(cols, options, strict=True):
        with col:
            active = current == value
            if st.button(
                label,
                key=f"{state_key}_btn_{value}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if not active:
                    st.session_state[state_key] = value
                    st.rerun()
    return str(st.session_state[state_key])


def clip_series_range(series: pd.DataFrame, range_key: str) -> pd.DataFrame:
    if series.empty or "date" not in series.columns:
        return series
    frame = series.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    end = frame["date"].max()
    days = {"1m": 30, "3m": 90}.get(range_key)
    if days is None:
        return frame.sort_values("date").reset_index(drop=True)
    start = end - pd.Timedelta(days=days)
    return frame.loc[frame["date"] >= start].sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_justtcg_series(tcgplayer_id: str) -> pd.DataFrame:
    """Live JustTCG NM history za product id (cache 1h)."""
    from justtcg_client import (
        batch_by_tcgplayer_ids,
        history_points_from_variant,
        justtcg_api_key,
        pick_nm_variant,
    )

    if not tcgplayer_id or not justtcg_api_key():
        return pd.DataFrame(columns=["date", "price"])
    try:
        rows = batch_by_tcgplayer_ids([str(tcgplayer_id)])
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    if not rows:
        return pd.DataFrame(columns=["date", "price"])
    variant = pick_nm_variant(list(rows[0].get("variants") or []))
    points = history_points_from_variant(variant)
    if not points:
        return pd.DataFrame(columns=["date", "price"])
    frame = pd.DataFrame(points)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["price"].astype(float)
    return frame.sort_values("date").reset_index(drop=True)


def render_market_detail(history: pd.DataFrame, market: pd.DataFrame, model, card_id: str) -> None:
    from database import get_card
    from justtcg_client import justtcg_api_key

    card = market.loc[market["id"] == card_id].iloc[0]
    db_card = get_card(str(card_id))
    tcgplayer_id = None
    if db_card is not None and db_card.tcgplayer_id:
        tcgplayer_id = str(db_card.tcgplayer_id)

    market_series = card_history(history, str(card["id"]))
    if market_series.empty:
        st.error(t("no_history_card"))
        return

    # AI uvijek na market/DB seriji (trenutni model).
    last_price = float(market_series["price"].iloc[-1])
    previous_price = (
        float(market_series["price"].iloc[-2]) if len(market_series) > 1 else last_price
    )
    predicted = predict_next_close(
        model,
        market_series,
        float(card["rarity_encoded"]),
        float(card["supertype_encoded"]),
    )
    if predicted is None:
        st.warning(t("short_series"))
        predicted = float(card["predicted_price"])
    change_pct = (predicted - last_price) / last_price * 100.0
    lags = lag_features_for_last_day(market_series) or {
        "price_lag_1": float(card.get("price_lag_1", last_price)),
        "rolling_mean_7": float(card.get("rolling_mean_7", last_price)),
    }
    day_change_pct = (
        (last_price - previous_price) / previous_price * 100.0 if previous_price else 0.0
    )
    signal = trading_signal(last_price, predicted)
    next_day = (pd.Timestamp(market_series["date"].iloc[-1]) + pd.Timedelta(days=1)).strftime(
        "%d.%m.%Y"
    )
    delta_cls = "up" if day_change_pct > 0.05 else "down" if day_change_pct < -0.05 else "flat"
    image = escape(card_image_for_id(str(card["id"])), quote=True)

    # Desktop: ~1/3 karta+AI | ~2/3 compare graf (kao TCG Forecast).
    left, right = st.columns([1.05, 2.15], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="detail-hero">
              <img src="{image}" alt="{escape(str(card['name']))}"
                   onerror="this.style.opacity='0.25';" />
              <div class="detail-hero-copy">
                <div class="detail-hero-title">{escape(str(card['name']))}</div>
                <div class="detail-hero-meta">{escape(str(card['set_name']))} · {escape(str(card['rarity']))} · {escape(str(card['id']))}</div>
                <div class="detail-hero-price">{escape(money(last_price))}</div>
                <div class="detail-hero-delta {delta_cls}">{day_change_pct:+.2f}% · {escape(signal_label(signal))}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        chip_row(
            [
                ("60d min", money(float(market_series["price"].min()), digits=4)),
                ("60d max", money(float(market_series["price"].max()), digits=4)),
            ],
            "stat-row",
        )
        st.markdown(
            f'<div class="detail-ai-head"><h3>{escape(t("ai_prediction"))}</h3></div>',
            unsafe_allow_html=True,
        )
        st.metric(
            t("price_on", date=next_day),
            money(predicted, digits=4),
            delta=f"{money_delta(predicted - last_price)} ({change_pct:+.2f}%)",
        )
        st.markdown(
            f'<div class="{SIGNAL_CLASS[signal]}">{signal_label(signal)}'
            f'<div class="signal-pct">{change_pct:+.2f}%</div></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("ai_caption", band=HOLD_BAND * 100))
        st.dataframe(
            pd.DataFrame(
                {
                    t("field"): [
                        t("points_series"),
                        t("price_yesterday"),
                        t("rolling_7d"),
                    ],
                    t("value"): [
                        str(len(market_series)),
                        money(float(lags["price_lag_1"]), digits=4),
                        money(float(lags["rolling_mean_7"]), digits=4),
                    ],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    with right:
        st.markdown(
            f"""
            <div class="compare-head">
              <h3>{escape(t("compare_history"))}</h3>
              <p class="compare-caption">{escape(t("compare_history_caption"))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        r1, r2 = st.columns([1.1, 1.5])
        with r1:
            st.caption(t("chart_range"))
            range_key = render_pill_toggle(
                [("1m", "1M"), ("3m", "3M"), ("all", t("chart_range_all"))],
                state_key=f"detail_range_{card_id}",
                default="1m",
            )
        with r2:
            st.caption(t("price_source"))
            source_key = render_pill_toggle(
                [("tcgplayer", "TCGplayer"), ("justtcg", "JustTCG")],
                state_key=f"detail_source_{card_id}",
                default="justtcg" if justtcg_api_key() else "tcgplayer",
            )

        just_series = pd.DataFrame(columns=["date", "price"])
        if source_key == "justtcg":
            if tcgplayer_id and justtcg_api_key():
                with st.spinner(t("loading_justtcg")):
                    just_series = load_justtcg_series(tcgplayer_id)
            chart_series = clip_series_range(just_series, range_key)
            source_label = "JustTCG"
            line_color = "#60a5fa"
            available = not chart_series.empty
            latest_src = float(chart_series["price"].iloc[-1]) if available else None
            meta_note = t("source_nm_usd")
            if not justtcg_api_key():
                st.info(t("justtcg_key_missing"))
            elif not tcgplayer_id:
                st.info(t("justtcg_no_product_id"))
            elif not available:
                st.info(t("source_unavailable"))
        else:
            chart_series = clip_series_range(market_series, range_key)
            source_label = "TCGplayer"
            line_color = "#f87171"
            available = not chart_series.empty
            latest_src = float(chart_series["price"].iloc[-1]) if available else None
            meta_note = t("source_market_db")

        st.plotly_chart(
            price_chart(
                chart_series,
                predicted if source_key == "tcgplayer" else None,
                str(card["name"]),
                source_label=source_label,
                show_ai=(source_key == "tcgplayer"),
                line_color=line_color,
            ),
            width="stretch",
        )

        src_price_html = (
            f'<div class="src-price">{escape(money(latest_src))}</div>'
            if latest_src is not None
            else ""
        )
        st.markdown(
            f"""
            <div class="source-card">
              <div class="src-title">{escape(t('source_label', name=source_label))}</div>
              <p class="src-meta">{escape(meta_note)} · {len(chart_series)} {escape(t('points_series').lower())}</p>
              {src_price_html}
            </div>
            """,
            unsafe_allow_html=True,
        )



def explore_card_html(row) -> str:
    """Cijela Collectr kartica (klik hvata nevidljivi Streamlit gumb + JS)."""
    name = escape(str(getattr(row, "name", "")))
    set_name = escape(str(getattr(row, "set_name", "") or ""))
    rarity = escape(str(getattr(row, "rarity", "") or ""))
    price = float(getattr(row, "price", 0.0) or 0.0)
    change = getattr(row, "expected_change_pct", None)
    card_id = str(getattr(row, "id", ""))
    image = escape(card_image_for_id(card_id), quote=True)
    if change is not None and pd.notna(change):
        change_f = float(change)
        cls = "up" if change_f > 0.05 else "down" if change_f < -0.05 else "flat"
        arrow = "▲" if change_f > 0.05 else "▼" if change_f < -0.05 else "●"
        change_html = (
            f'<div class="explore-card-change {cls}">'
            f"{arrow} {change_f:+.2f}%</div>"
        )
    else:
        change_html = '<div class="explore-card-change flat">—</div>'
    meta = " · ".join(part for part in (set_name, rarity) if part)
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


def select_explore_card(card_id: str) -> None:
    """Streamlit on_click — radi i lokalno i na Cloud (za razliku od HTML <a>)."""
    st.session_state["market_selected_id"] = str(card_id)
    st.session_state["nav_page"] = "market"
    st.session_state["market_detail_only"] = True


def apply_nav_query_params() -> None:
    """Opcionalni deep-link: ?nav=market&card=sv3-123."""
    qp = st.query_params
    card = qp.get("card")
    nav = qp.get("nav")
    if card is None and nav is None:
        return
    if card is not None:
        select_explore_card(str(card))
        if nav is not None:
            st.session_state["nav_page"] = str(nav)
    elif nav is not None:
        st.session_state["nav_page"] = str(nav)
    st.query_params.clear()


def render_navbar() -> str:
    """Collectr-style sticky header: brand | text links | lang + currency."""
    from currency import CURRENCY_EUR, CURRENCY_USD, get_currency, _set_currency
    from i18n import LANG_EN, LANG_HR, _set_lang, get_lang

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "explore"
    st.session_state.pop("nav_menu_open", None)

    pages = [
        ("explore", t("nav_explore")),
        ("market", t("nav_market")),
        ("portfolio", t("nav_portfolio")),
        ("scanner", t("nav_scanner")),
    ]

    cur = get_currency()
    lang = get_lang()
    code = "USD" if cur == CURRENCY_USD else "EUR"

    # brand | 4 links | spacer | HR EN | currency
    brand, *nav_cols, _gap, lang_hr, lang_en, cur_btn = st.columns(
        [1.35, 0.95, 1.15, 0.95, 1.05, 1.8, 0.45, 0.45, 0.7],
        vertical_alignment="center",
        gap="small",
    )
    with brand:
        st.markdown(
            f'<div class="nav-brand-left">TCG AI'
            f'<span>{escape(t("brand_tagline"))}</span></div>',
            unsafe_allow_html=True,
        )
    for col, (key, label) in zip(nav_cols, pages, strict=True):
        with col:
            active = st.session_state["nav_page"] == key
            if st.button(
                label,
                key=f"nav_{key}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if st.session_state["nav_page"] != key:
                    st.session_state["nav_page"] = key
                    st.rerun()
    with lang_hr:
        if st.button(
            "HR",
            key="nav_lang_hr",
            type="primary" if lang == LANG_HR else "secondary",
            use_container_width=True,
        ):
            if lang != LANG_HR:
                _set_lang(LANG_HR)
    with lang_en:
        if st.button(
            "EN",
            key="nav_lang_en",
            type="primary" if lang == LANG_EN else "secondary",
            use_container_width=True,
        ):
            if lang != LANG_EN:
                _set_lang(LANG_EN)
    with cur_btn:
        if st.button(
            code,
            key="nav_currency_pill",
            use_container_width=True,
            help="USD / EUR",
        ):
            _set_currency(CURRENCY_EUR if cur == CURRENCY_USD else CURRENCY_USD)

    return str(st.session_state["nav_page"])


def _reset_explore_price_keys() -> None:
    """Označi reset; stvarne granice se primijene u render_explore_price_box (prije widgeta)."""
    st.session_state["explore_price_do_reset"] = True


def render_explore_price_box(series: pd.Series) -> tuple[float, float]:
    """Kompaktan price range box za lijevi filter panel (min/max + slider)."""
    lo_usd, hi_usd = price_bounds(series)
    bound_lo = float(to_display(lo_usd))
    bound_hi = float(to_display(hi_usd))
    if bound_hi <= bound_lo:
        bound_hi = bound_lo + 1.0
    span = bound_hi - bound_lo
    step = 0.01 if span <= 20 else 0.5 if span <= 200 else 1.0

    range_key = "explore_price_slider"
    lo_key = "explore_price_lo"
    hi_key = "explore_price_hi"

    def _clamp(low: float, high: float) -> tuple[float, float]:
        low = min(max(float(low), bound_lo), bound_hi)
        high = min(max(float(high), bound_lo), bound_hi)
        if low > high:
            low, high = high, low
        return low, high

    # Reset / missing keys — postavi PRIJE widgeta (nikad pop tijekom on_change).
    if st.session_state.pop("explore_price_do_reset", False) or range_key not in st.session_state:
        st.session_state[range_key] = (bound_lo, bound_hi)
        st.session_state[lo_key] = bound_lo
        st.session_state[hi_key] = bound_hi

    raw = st.session_state.get(range_key, (bound_lo, bound_hi))
    try:
        low, high = _clamp(float(raw[0]), float(raw[1]))
    except (TypeError, ValueError, IndexError, KeyError):
        low, high = bound_lo, bound_hi
    st.session_state[range_key] = (low, high)
    st.session_state[lo_key] = low
    st.session_state[hi_key] = high

    def _from_slider() -> None:
        raw_pair = st.session_state.get(range_key)
        if raw_pair is None:
            return
        try:
            pair = _clamp(float(raw_pair[0]), float(raw_pair[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            return
        st.session_state[range_key] = pair
        st.session_state[lo_key] = pair[0]
        st.session_state[hi_key] = pair[1]

    def _from_min() -> None:
        low_v = st.session_state.get(lo_key, bound_lo)
        high_v = st.session_state.get(hi_key, bound_hi)
        try:
            low_v, high_v = _clamp(float(low_v), float(high_v))
        except (TypeError, ValueError):
            return
        if low_v > high_v:
            high_v = low_v
        st.session_state[range_key] = (low_v, high_v)
        st.session_state[lo_key] = low_v
        st.session_state[hi_key] = high_v

    def _from_max() -> None:
        low_v = st.session_state.get(lo_key, bound_lo)
        high_v = st.session_state.get(hi_key, bound_hi)
        try:
            low_v, high_v = _clamp(float(low_v), float(high_v))
        except (TypeError, ValueError):
            return
        if high_v < low_v:
            low_v = high_v
        st.session_state[range_key] = (low_v, high_v)
        st.session_state[lo_key] = low_v
        st.session_state[hi_key] = high_v

    st.slider(
        t("explore_price_box"),
        min_value=bound_lo,
        max_value=bound_hi,
        step=float(step),
        format=number_format_pattern(digits=2),
        key=range_key,
        label_visibility="collapsed",
        on_change=_from_slider,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            t("price_min"),
            min_value=bound_lo,
            max_value=bound_hi,
            step=float(step),
            format="%.2f",
            key=lo_key,
            on_change=_from_min,
        )
    with c2:
        st.number_input(
            t("price_max"),
            min_value=bound_lo,
            max_value=bound_hi,
            step=float(step),
            format="%.2f",
            key=hi_key,
            on_change=_from_max,
        )
    low, high = st.session_state.get(range_key, (bound_lo, bound_hi))
    return from_display(float(low)), from_display(float(high))


def render_explore_grid(rows: pd.DataFrame, cols_per_row: int = 4) -> None:
    items = list(rows.itertuples(index=False))
    if not items:
        st.info(t("explore_empty"))
        return
    for start in range(0, len(items), cols_per_row):
        chunk = items[start : start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, row in zip(cols, chunk, strict=False):
            with col:
                card_id = str(row.id)
                st.markdown(explore_card_html(row), unsafe_allow_html=True)
                # Label se sakrije JS-om; hit-target prekriva cijelu karticu.
                st.button(
                    "card",
                    key=f"explore_open_{card_id}",
                    use_container_width=True,
                    help=t("click_card_ai"),
                    on_click=select_explore_card,
                    args=(card_id,),
                )
    components.html(
        f"<script>{EXPLORE_CARD_HIT_JS}</script>",
        height=0,
        width=0,
    )


def render_explore(market: pd.DataFrame) -> None:
    """Početna Explore stranica — Collectr layout: search, sort, lijevi filteri, infinite grid."""
    s1, s2, s3 = st.columns([4.2, 1.0, 0.9])
    with s1:
        query = st.text_input(
            t("search"),
            placeholder=t("explore_search_ph"),
            key="explore_query",
            label_visibility="collapsed",
        )
    with s2:
        st.button(
            t("explore_search_btn"),
            key="explore_go_btn",
            type="primary",
            use_container_width=True,
        )
    with s3:
        if st.button(t("explore_clear"), key="explore_clear_btn", use_container_width=True):
            st.session_state["explore_query"] = ""
            _reset_explore_price_keys()
            st.session_state["explore_shown"] = EXPLORE_BATCH
            st.rerun()

    sort_options = ["name", "price_desc", "price_asc", "exp_desc", "exp_asc"]
    sort_labels = {
        "name": t("sort_name"),
        "price_desc": t("sort_price_desc"),
        "price_asc": t("sort_price_asc"),
        "exp_desc": t("sort_exp_desc"),
        "exp_asc": t("sort_exp_asc"),
    }
    sort_col, _ = st.columns([1.4, 3.6])
    with sort_col:
        sort_by = st.selectbox(
            t("explore_sort_by"),
            sort_options,
            format_func=lambda k: sort_labels[k],
            key="explore_sort",
        )

    left, right = st.columns([1.05, 3.2], gap="large")
    with left:
        st.markdown(
            f'<div class="explore-filter-panel"><h4>{escape(t("explore_filters"))}</h4>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="explore-filter-label">{escape(t("explore_category"))}</div>',
            unsafe_allow_html=True,
        )
        # Widget key mora biti drugačiji od i18n ključa — inače Streamlit zna pokazati raw key.
        st.checkbox(
            t("explore_cat_pokemon"),
            value=True,
            disabled=True,
            key="exp_pokemon_cb",
        )
        st.markdown(
            f'<div class="explore-filter-label">{escape(t("explore_price_box"))} ({escape(currency_code())})</div>',
            unsafe_allow_html=True,
        )
        price_min, price_max = render_explore_price_box(market["price"])
        if st.button(t("explore_reset"), key="explore_reset_filters", use_container_width=True):
            _reset_explore_price_keys()
            st.session_state["explore_query"] = ""
            st.session_state["explore_shown"] = EXPLORE_BATCH
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    filtered = filter_market_frame(
        market,
        query=query or "",
        set_name=FILTER_ALL_SETS,
        rarity=FILTER_ALL,
        signal=FILTER_ALL,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max,
    )

    fingerprint = f"{query}|{sort_by}|{price_min}|{price_max}"
    if st.session_state.get("explore_filter_fp") != fingerprint:
        st.session_state["explore_filter_fp"] = fingerprint
        st.session_state["explore_shown"] = EXPLORE_BATCH
    if "explore_shown" not in st.session_state:
        st.session_state["explore_shown"] = EXPLORE_BATCH

    shown_n = min(int(st.session_state["explore_shown"]), len(filtered))
    page_rows = filtered.iloc[:shown_n]

    with right:
        st.caption(t("explore_results", n=len(filtered)))
        if filtered.empty:
            st.warning(t("explore_empty"))
        else:
            render_explore_grid(page_rows, cols_per_row=5)
            if shown_n < len(filtered):
                if st.button(
                    t("explore_load_more"),
                    key="explore_load_more",
                    use_container_width=True,
                ):
                    st.session_state["explore_shown"] = shown_n + EXPLORE_BATCH
                    st.rerun()
                components.html(
                    f"<script>{EXPLORE_INFINITE_SCROLL_JS}</script>",
                    height=1,
                    width=1,
                )
            else:
                st.caption(t("explore_end"))


def render_market(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    selected_id = st.session_state.get("market_selected_id")
    market_ids = set(market["id"].astype(str))
    if (
        st.session_state.get("market_detail_only")
        and selected_id is not None
        and str(selected_id) in market_ids
    ):
        if st.button(t("back_explore"), key="market_back_explore"):
            st.session_state["market_detail_only"] = False
            st.session_state["nav_page"] = "explore"
            st.rerun()
        render_market_detail(history, market, model, str(selected_id))
        return

    st.subheader(t("market_title"))
    counts = market["signal"].value_counts() if "signal" in market.columns else {}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("cards"), len(market))
    m2.metric(signal_label("KUPI"), int(counts.get("KUPI", 0)))
    m3.metric(signal_label("DRŽI"), int(counts.get("DRŽI", 0)))
    m4.metric(signal_label("PRODAJ"), int(counts.get("PRODAJ", 0)))

    f1, f2, f3, f4, f5 = st.columns([1.6, 1.2, 1, 1, 1])
    query = f1.text_input(t("search"), placeholder=t("search_ph"), key="market_query")
    sets = [FILTER_ALL_SETS] + sorted(market["set_name"].dropna().unique().tolist())
    set_filter = f2.selectbox(
        t("set"),
        sets,
        format_func=lambda s: t("all_sets") if s == FILTER_ALL_SETS else s,
        key="market_set",
    )
    rarities = [FILTER_ALL] + sorted(market["rarity"].dropna().unique().tolist())
    rarity_filter = f3.selectbox(
        t("rarity"),
        rarities,
        format_func=lambda r: t("all") if r == FILTER_ALL else r,
        key="market_rarity",
    )
    signal_options = [FILTER_ALL, "KUPI", "PRODAJ", "DRŽI"]
    signal_filter = f4.selectbox(
        t("signal"),
        signal_options,
        format_func=lambda s: t("all") if s == FILTER_ALL else signal_label(s),
        key="market_signal",
    )
    sort_options = ["name", "price_desc", "price_asc", "exp_desc", "exp_asc"]
    sort_labels = {
        "name": t("sort_name"),
        "price_desc": t("sort_price_desc"),
        "price_asc": t("sort_price_asc"),
        "exp_desc": t("sort_exp_desc"),
        "exp_asc": t("sort_exp_asc"),
    }
    sort_by = f5.selectbox(
        t("sort"),
        sort_options,
        format_func=lambda k: sort_labels[k],
        key="market_sort",
    )
    price_min, price_max = render_price_slider("market_price", market["price"])

    filtered = filter_market_frame(
        market,
        query=query,
        set_name=set_filter,
        rarity=rarity_filter,
        signal=signal_filter,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max,
    )

    filter_fingerprint = (
        f"{query}|{set_filter}|{rarity_filter}|{signal_filter}|{sort_by}|{price_min}|{price_max}"
    )
    if st.session_state.get("market_filter_fp") != filter_fingerprint:
        st.session_state["market_filter_fp"] = filter_fingerprint
        st.session_state["market_page"] = 1

    p1, p2 = st.columns([1, 3])
    page_size = int(
        p1.selectbox(t("per_page"), [12, 24, 48, 96], index=1, key="market_page_size")
    )
    p2.caption(t("filtered_of", n=len(filtered), total=len(market)))

    page = int(st.session_state.get("market_page", 1))
    page_rows, page, pages = paginate_frame(filtered, page, page_size)
    st.session_state["market_page"] = page
    render_pager("market", page, pages, len(filtered), page_size)

    st.markdown(f"##### {t('grid_cards')}")
    if filtered.empty:
        st.warning(t("no_cards_filters"))
    else:
        render_market_grid(page_rows, selection_key="market_selected_id")

    st.divider()
    st.markdown(f"##### {t('detail_ai')}")
    if filtered.empty:
        return

    filtered_ids = set(filtered["id"].astype(str))
    selected_id = st.session_state.get("market_selected_id")
    if selected_id is not None and str(selected_id) not in filtered_ids:
        selected_id = None
        st.session_state.pop("market_selected_id", None)

    if not selected_id:
        st.info(t("click_card_ai"))
        return

    render_market_detail(history, market, model, str(selected_id))

@st.cache_data(show_spinner=False)
def build_ai_scan(history: pd.DataFrame, market: pd.DataFrame, _model) -> pd.DataFrame:
    """Za svaku kartu: lagovi → XGBoost → cijena za 7 dana i ROI.

    history iz load_exchange već je dnevno resamplean, pa ovdje samo filtriramo.
    """
    rows: list[dict] = []
    for card in market.itertuples(index=False):
        series = (
            history.loc[history["card_id"] == card.id]
            .sort_values("date")
            .reset_index(drop=True)
        )
        if series.empty:
            continue
        current = float(series["price"].iloc[-1])
        if current <= 0:
            continue
        week_price = forecast_price_in_days(
            _model,
            series,
            float(card.rarity_encoded),
            float(card.supertype_encoded),
        )
        if week_price is None:
            continue
        target = float(week_price)
        rows.append(
            {
                "Naziv": str(card.name),
                "Set": str(card.set_name),
                "Trenutna cijena": current,
                "AI Ciljna cijena": target,
                "Očekivani ROI (%)": (target - current) / current * 100.0,
                "id": str(card.id),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["Naziv", "Set", "Trenutna cijena", "AI Ciljna cijena", "Očekivani ROI (%)", "id"]
        )
    return pd.DataFrame(rows).sort_values("Očekivani ROI (%)", ascending=False).reset_index(drop=True)


def scanner_table(frame: pd.DataFrame, height: int = 320) -> None:
    cols = [c for c in ["Naziv", "Set", "Rijetkost", "Trenutna cijena", "AI Ciljna cijena", "Očekivani ROI (%)"] if c in frame.columns]
    display = frame[cols].copy()
    for price_col in ("Trenutna cijena", "AI Ciljna cijena"):
        if price_col in display.columns:
            display[price_col] = pd.to_numeric(display[price_col], errors="coerce").map(to_display)
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={
            "Naziv": st.column_config.TextColumn(t("col_name"), width="medium"),
            "Set": st.column_config.TextColumn(t("set"), width="medium"),
            "Rijetkost": st.column_config.TextColumn(t("rarity"), width="small"),
            "Trenutna cijena": st.column_config.NumberColumn(
                t("col_current"),
                format=number_format_pattern(digits=4),
            ),
            "AI Ciljna cijena": st.column_config.NumberColumn(
                t("col_ai_target"),
                format=number_format_pattern(digits=4),
            ),
            "Očekivani ROI (%)": st.column_config.NumberColumn(t("col_roi"), format="%+.2f%%"),
        },
    )


def _scanner_page_block(prefix: str, frame: pd.DataFrame, page_size: int) -> None:
    """Grid + tablica + pager za jednu scanner sekciju."""
    if frame.empty:
        return
    fp_key = f"{prefix}_fp"
    fingerprint = f"{len(frame)}|{page_size}|{frame.iloc[0]['id'] if 'id' in frame.columns else ''}"
    if st.session_state.get(fp_key) != fingerprint:
        st.session_state[fp_key] = fingerprint
        st.session_state[f"{prefix}_page"] = 1

    page = int(st.session_state.get(f"{prefix}_page", 1))
    page_rows, page, pages = paginate_frame(frame, page, page_size)
    st.session_state[f"{prefix}_page"] = page
    render_pager(prefix, page, pages, len(frame), page_size)

    # Grid očekuje name/set_name/price/expected_change_pct
    grid = page_rows.rename(
        columns={
            "id": "id",
            "Naziv": "name",
            "Set": "set_name",
            "Rijetkost": "rarity",
            "Trenutna cijena": "price",
            "Očekivani ROI (%)": "expected_change_pct",
        }
    )
    render_market_grid(grid, cols_per_row=6)
    with st.expander(t("table_page"), expanded=False):
        scanner_table(page_rows, height=min(360, 48 + 36 * len(page_rows)))


def render_scanner(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader(t("scanner_title"))
    st.caption(t("scanner_caption", days=FORECAST_DAYS))

    f1, f2, f3, f4, f5 = st.columns([1.4, 1.2, 1, 1, 0.9])
    query = f1.text_input(t("search"), placeholder=t("search_ph_name"), key="scanner_query")
    sets = [FILTER_ALL_SETS] + sorted(market["set_name"].dropna().unique().tolist())
    set_filter = f2.selectbox(
        t("set"),
        sets,
        format_func=lambda s: t("all_sets") if s == FILTER_ALL_SETS else s,
        key="scanner_set",
    )
    rarities = [FILTER_ALL] + sorted(market["rarity"].dropna().unique().tolist())
    rarity_filter = f3.selectbox(
        t("rarity"),
        rarities,
        format_func=lambda r: t("all") if r == FILTER_ALL else r,
        key="scanner_rarity",
    )
    min_growth = f4.number_input(
        t("min_growth_top"),
        min_value=0.0,
        max_value=100.0,
        value=float(SCANNER_GROWTH_FLOOR),
        step=1.0,
        key="scanner_min_growth",
    )
    page_size = int(f5.selectbox(t("per_page"), [12, 24, 48], index=1, key="scanner_page_size"))
    # Bounds from market quotes so the slider is available before the scan finishes.
    price_min, price_max = render_price_slider("scanner_price", market["price"])

    with st.spinner(t("scanning")):
        scan = build_ai_scan(history, market, model)

    if scan.empty:
        st.warning(t("no_scan_history"))
        return

    # Dopuni rarity iz market tablica za filter/grid.
    if "Rijetkost" not in scan.columns and "rarity" in market.columns:
        scan = scan.merge(
            market[["id", "rarity"]].rename(columns={"rarity": "Rijetkost"}),
            on="id",
            how="left",
        )

    scoped = scan
    if set_filter != FILTER_ALL_SETS:
        scoped = scoped.loc[scoped["Set"] == set_filter]
    if rarity_filter != FILTER_ALL and "Rijetkost" in scoped.columns:
        scoped = scoped.loc[scoped["Rijetkost"] == rarity_filter]
    if query.strip():
        q = query.strip()
        scoped = scoped.loc[scoped["Naziv"].astype(str).str.contains(q, case=False, na=False)]
    scoped = apply_price_range(scoped, "Trenutna cijena", price_min, price_max)

    if scoped.empty:
        st.warning(t("no_cards_filters"))
        return

    opportunities = (
        scoped.loc[scoped["Očekivani ROI (%)"] >= float(min_growth)]
        .sort_values("Očekivani ROI (%)", ascending=False)
        .reset_index(drop=True)
    )
    warnings_df = (
        scoped.loc[scoped["Očekivani ROI (%)"] < 0]
        .sort_values("Očekivani ROI (%)", ascending=True)
        .reset_index(drop=True)
    )

    k1, k2, k3 = st.columns(3)
    k1.metric(t("scanned_filtered"), len(scoped))
    k2.metric(t("top_opps"), len(opportunities), delta=f"≥ {min_growth:.0f}%")
    k3.metric(t("drop_warnings"), len(warnings_df))

    st.markdown(
        f'<div class="scanner-title">{t("top_opps_heading", pct=min_growth)}</div>',
        unsafe_allow_html=True,
    )
    if opportunities.empty:
        st.info(t("no_top_opps", pct=min_growth))
    else:
        _scanner_page_block("scan_top", opportunities, page_size)

    st.markdown(
        f'<div class="scanner-title">{t("drop_heading")}</div>',
        unsafe_allow_html=True,
    )
    if warnings_df.empty:
        st.success(t("no_drop_warnings"))
    else:
        _scanner_page_block("scan_warn", warnings_df, page_size)


def render_portfolio(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader(t("add_card"))
    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  {money(float(row.price))}"
        for row in market.sort_values("name").itertuples(index=False)
    }
    with st.form("add_portfolio", clear_on_submit=True):
        picked, quantity, purchase_price = st.columns([2, 1, 1])
        card_id = picked.selectbox(
            t("card"),
            options=list(labels.keys()),
            format_func=lambda item: labels[item],
        )
        qty = quantity.number_input(t("quantity"), min_value=1, step=1, value=1)
        cost_display = purchase_price.number_input(
            t("purchase_price", code=currency_code()),
            min_value=0.0001,
            step=0.01,
            value=float(to_display(0.10)),
            format="%.4f",
        )
        submitted = st.form_submit_button(t("add_to_portfolio"), type="primary")

    if submitted:
        try:
            add_portfolio_position(str(card_id), int(qty), float(from_display(cost_display)))
        except ValueError as exc:
            st.error(str(exc))
        else:
            name = str(market.loc[market["id"] == card_id, "name"].iloc[0])
            st.session_state["portfolio_notice"] = t("added_to_portfolio", name=name)
            st.rerun()

    notice = st.session_state.pop("portfolio_notice", None)
    if notice:
        st.success(notice)

    lots = load_portfolio_lots()
    if lots.empty:
        render_portfolio_kpis(0.0, 0.0, 0.0, 0.0)
        st.info(t("portfolio_empty"))
        return

    view = portfolio_view(lots, market, history, model)
    value = float(view["market_value"].sum())
    invested = float(view["invested"].sum())
    pnl = float(view["pnl"].sum())
    pnl_pct = pnl / invested * 100.0 if invested else 0.0
    render_portfolio_kpis(value, invested, pnl, pnl_pct)
    render_week_outlook(value, float(view["week_value"].sum()))

    render_portfolio_gallery(view)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    apply_nav_query_params()
    page = render_navbar()

    from config import get_supabase_credentials

    url, key = get_supabase_credentials()
    if not url or not key:
        st.error(t("missing_supabase"))
        st.markdown(
            """
**Streamlit Cloud → ⋮ Manage app → Settings → Secrets**  
zalijepi točno ovaj TOML (zamijeni vrijednosti), **Save**, pa **Reboot**:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SERVICE_ROLE_KEY"
```

Ključeve: Supabase → **Project Settings → API**  
(`Project URL` + `service_role`).

**Važno:** URL mora biti samo `https://xxxx.supabase.co` —  
**bez** `/rest/v1` na kraju (inače greška PGRST125).
"""
        )
        return


    try:
        history, market, model = load_exchange()
    except RuntimeError as exc:
        st.error(str(exc))
        message = str(exc).lower()
        if "tablice" in message or "schema" in message or "cards" in message:
            from database import SCHEMA_SQL

            st.markdown(
                """
### Kreiraj tablice u Supabaseu
1. Otvori [Supabase Dashboard](https://supabase.com/dashboard) → svoj projekt  
2. Lijevo: **SQL Editor** → **New query**  
3. Kopiraj SQL ispod → zalijepi → **Run**  
4. **Table Editor**: moraš vidjeti `cards`, `price_history`, `portfolio`  
5. Ako app i dalje javlja grešku: **Project Settings → API → Reload schema**  
6. Streamlit → **Reboot**
"""
            )
            st.code(SCHEMA_SQL, language="sql")
        else:
            st.info(t("check_secrets"))
        return
    if market.empty or history.empty:
        st.error(t("no_price_history"))
        return

    if page == "explore":
        render_explore(market)
    elif page == "market":
        render_market(history, market, model)
    elif page == "portfolio":
        render_portfolio(history, market, model)
    else:
        render_scanner(history, market, model)


if __name__ == "__main__":
    main()
