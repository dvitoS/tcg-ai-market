"""Global Streamlit CSS tokens and layout."""

from __future__ import annotations

import streamlit as st

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
    :root {
        --bg0: #070b14;
        --bg1: #0b1220;
        --bg2: #132238;
        --panel: #132033;
        --border: #24364d;
        --text: #e8eef8;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --accent-2: #60a5fa;
        --buy: #22c55e;
        --sell: #f87171;
        --hold: #fbbf24;
        --radius: 14px;
        --font-ui: "DM Sans", "Segoe UI", system-ui, sans-serif;
        --font-display: "Fraunces", Georgia, serif;
    }
    .stApp {
        background: radial-gradient(circle at top left, var(--bg2) 0%, var(--bg1) 45%, var(--bg0) 100%);
        font-family: var(--font-ui);
    }
    .skel-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 14px 12px;
        margin: 8px 0 16px;
    }
    .skel-card {
        border-radius: 10px;
        overflow: hidden;
        background: rgba(19, 32, 51, 0.85);
        border: 1px solid rgba(36, 54, 77, 0.9);
    }
    .skel-img {
        aspect-ratio: 63 / 88;
        background: linear-gradient(90deg, rgba(255,255,255,0.04), rgba(255,255,255,0.10), rgba(255,255,255,0.04));
        background-size: 200% 100%;
        animation: skel-shine 1.2s ease-in-out infinite;
    }
    .skel-line {
        height: 10px;
        margin: 10px 10px 6px;
        border-radius: 6px;
        background: rgba(148, 163, 184, 0.18);
    }
    .skel-line.short { width: 55%; }
    .skel-chart {
        height: 280px;
        border-radius: 12px;
        border: 1px solid rgba(36, 54, 77, 0.9);
        background: linear-gradient(90deg, rgba(255,255,255,0.03), rgba(255,255,255,0.08), rgba(255,255,255,0.03));
        background-size: 200% 100%;
        animation: skel-shine 1.2s ease-in-out infinite;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #94a3b8 !important;
        font-size: 0.9rem;
    }
    @keyframes skel-shine {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    @media (prefers-reduced-motion: reduce) {
        .skel-img, .skel-chart { animation: none; }
    }
    h1, h2, h3, p, label, span, div { color: var(--text) !important; }
    [data-testid="stSidebar"] { background: #0d1626; border-right: 1px solid var(--border); }
    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 12px 16px;
    }
    .source-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 6px 0 10px;
    }
    .source-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(19, 32, 51, 0.9);
        font-size: 0.75rem;
        font-weight: 650;
        letter-spacing: 0.02em;
        color: var(--muted) !important;
    }
    .source-badge.live { border-color: rgba(56, 189, 248, 0.55); color: #7dd3fc !important; }
    .source-badge.saved { border-color: rgba(251, 191, 36, 0.45); color: #fde68a !important; }
    .source-badge.spot { border-color: rgba(196, 181, 253, 0.45); color: #ddd6fe !important; }
    .source-badge.db { border-color: rgba(248, 113, 113, 0.45); color: #fecaca !important; }
    .ai-explain {
        margin-top: 10px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.65);
        font-size: 0.88rem;
        line-height: 1.45;
    }
    .ai-explain .ai-conf { color: var(--muted) !important; margin-bottom: 6px; font-weight: 650; }
    .ai-move-label {
        font-size: 0.8rem;
        opacity: 0.75;
        margin-bottom: 4px;
    }
    .ai-move-value {
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-bottom: 10px;
    }
    .catalog-hero-search { margin-bottom: 0.35rem; }
    .market-tile, .explore-card {
        transition: transform 0.18s ease, border-color 0.15s ease, background 0.15s ease;
    }
    .market-tile:hover, div[data-testid="stColumn"]:has(.explore-card):hover .explore-card {
        transform: translateY(-2px) scale(1.01);
    }
    @media (max-width: 768px) {
        .market-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 12px 10px; }
        .detail-hero { flex-direction: column; }
        .nav-brand-left { letter-spacing: 0.12em; font-size: 1rem; }
        .pokemon-card-transformer { --card-w: 150px; }
        div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) {
            flex-wrap: wrap !important;
            min-height: auto;
            padding: 0.5rem 0.2rem;
        }
        div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) button {
            font-size: 0.8rem !important;
            min-height: 2rem !important;
            height: 2rem !important;
            padding: 0.3rem 0.45rem !important;
        }
        .explore-card, .market-tile { font-size: 0.9rem; }
        .pokemon-card-stage:hover .pokemon-card-transformer,
        .pokemon-card-stage:focus-within .pokemon-card-transformer {
            transform: none;
        }
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
    .market-tile-meta.low-conf {
        color: var(--muted);
        opacity: 0.85;
        font-size: 0.72rem;
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
    .market-tile-signal.BUY, .market-tile-signal.KUPI { background: #14532d; border: 1px solid #22c55e; color: #dcfce7 !important; }
    .market-tile-signal.SELL, .market-tile-signal.PRODAJ { background: #7f1d1d; border: 1px solid #f87171; color: #fee2e2 !important; }
    .market-tile-signal.HOLD, .market-tile-signal.DRZI, .market-tile-signal.DRŽI { background: #78350f; border: 1px solid #fbbf24; color: #fef3c7 !important; }
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
        font-family: var(--font-display), Georgia, serif;
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
        font-family: var(--font-ui), system-ui, sans-serif;
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
        gap: 0.55rem !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        min-height: 3.5rem;
        padding: 0.65rem 0.35rem 0.7rem;
        margin: 0.85rem 0 1rem;
        background: rgba(10, 10, 10, 0.92) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left)
        > div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
    /* Ghost text links (not pills) */
    div[data-testid="stHorizontalBlock"]:has(.nav-brand-left) button {
        border-radius: 8px !important;
        font-family: var(--font-ui), system-ui, sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        letter-spacing: 0 !important;
        padding: 0.4rem 0.7rem !important;
        min-height: 2.15rem !important;
        height: 2.15rem !important;
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
        padding-top: 1.15rem !important;
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
    /* Filters boxed under "Filteri" — don't stretch / don't paint over grid */
    div[data-testid="stHorizontalBlock"]:has(.explore-filter-head) {
        align-items: flex-start !important;
        background: transparent !important;
    }
    div[data-testid="stColumn"]:has(.explore-filter-head) {
        align-self: flex-start !important;
        height: auto !important;
        background: transparent !important;
    }
    div[data-testid="stColumn"]:has(.explore-card) {
        background: transparent !important;
    }
    div[data-testid="stVerticalBlock"]:has(.explore-card) {
        background: transparent !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.explore-filter-head) {
        background: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 14px !important;
        padding: 4px 2px 6px !important;
        height: fit-content !important;
        overflow: visible !important;
    }
    .explore-filter-head h4 {
        margin: 2px 0 8px !important;
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
        margin: 10px 0 6px;
    }
    .explore-card {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 13px 10px 14px;
        text-align: center;
        height: 100%;
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
        border-color: rgba(255, 255, 255, 0.10);
        background: rgba(255, 255, 255, 0.04);
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
    .chart-price-head {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
        margin: 0.35rem 0 0.15rem;
        padding: 0 2px;
    }
    .chart-price-head .chart-price-label {
        color: #94a3b8 !important;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin: 0;
    }
    .chart-price-head .chart-price-counter {
        color: #f8fafc !important;
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.15;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.02em;
        margin: 0;
        transition: color 0.15s ease;
    }
    .chart-price-head .chart-price-counter.is-hover {
        color: #93c5fd !important;
    }
    .chart-price-head .chart-price-date {
        color: #64748b !important;
        font-size: 0.78rem;
        margin: 0;
        min-height: 1.1em;
    }
    .ebay-block {
        margin-top: 1.5rem;
        padding-top: 0.25rem;
    }
    .ebay-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 10px;
    }
    .ebay-row {
        display: grid;
        grid-template-columns: 40px minmax(0, 1fr) auto auto;
        gap: 10px 12px;
        align-items: center;
        padding: 10px 12px;
        background: rgba(10, 14, 24, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        min-height: 0;
    }
    .ebay-row .ebay-thumb {
        width: 40px;
        height: 40px;
        border-radius: 6px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.06);
        flex-shrink: 0;
    }
    .ebay-row .ebay-thumb img {
        width: 40px;
        height: 40px;
        object-fit: cover;
        display: block;
    }
    .ebay-row .ebay-title {
        color: #e2e8f0 !important;
        font-size: 0.9rem;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .ebay-row .ebay-meta {
        color: #94a3b8 !important;
        font-size: 0.75rem;
        margin-top: 2px;
    }
    .ebay-row .ebay-price {
        color: #f8fafc !important;
        font-weight: 700;
        white-space: nowrap;
    }
    .ebay-row a.ebay-link {
        color: #93c5fd !important;
        font-weight: 600;
        text-decoration: none;
        white-space: nowrap;
    }
    .ebay-row a.ebay-link:hover { text-decoration: underline; }
    @media (max-width: 720px) {
        .ebay-row {
            grid-template-columns: 40px minmax(0, 1fr) auto;
            grid-template-areas:
                "thumb title title"
                "thumb price link";
        }
        .ebay-row .ebay-thumb { grid-area: thumb; }
        .ebay-row .ebay-copy { grid-area: title; }
        .ebay-row .ebay-price { grid-area: price; }
        .ebay-row a.ebay-link { grid-area: link; }
    }
</style>
"""


def inject_app_styles() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
