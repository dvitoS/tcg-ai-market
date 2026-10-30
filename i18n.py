"""English UI strings for Streamlit."""

from __future__ import annotations

from typing import Any

_TEXT: dict[str, str] = {

        "app_title": "📈 TCG AI Market Dashboard",
        "app_caption": "Pokémon TCG market · portfolio · XGBoost forecasts",
        "tab_market": "Market & AI",
        "tab_portfolio": "My Portfolio",
        "tab_scanner": "🤖 AI Scanner",
        "nav_explore": "Catalog",
        "nav_market": "Market & AI",
        "nav_portfolio": "Portfolio",
        "nav_scanner": "AI Scanner",
        "nav_watchlist": "Watchlist",
        "catalog_mode": "Mode",
        "catalog_browse": "Browse",
        "catalog_signals": "AI signals",
        "explore_find": "Find a Product",
        "explore_search_ph": "Search cards, sets…",
        "explore_search_btn": "Search",
        "explore_clear": "Clear",
        "explore_sort_by": "Sort by:",
        "explore_filters": "Filters",
        "explore_category": "Category",
        "explore_cat_pokemon": "Pokémon",
        "explore_price_box": "Price Range",
        "explore_reset": "Reset All",
        "explore_results": "{n} results",
        "explore_load_more": "Load more",
        "explore_end": "End of results",
        "explore_empty": "No cards match these filters.",
        "brand_tagline": "Collect. Track. Predict.",
        "badge_live": "Live JustTCG",
        "badge_saved": "Saved history",
        "badge_spot": "Spot only",
        "badge_db": "TCGplayer DB",
        "chart_overlay": "Overlay sources",
        "chart_compare_all": "Compare all",
        "watchlist_add": "Add to watchlist",
        "watchlist_remove": "Remove from watchlist",
        "watchlist_added": "Added to watchlist.",
        "watchlist_removed": "Removed from watchlist.",
        "watchlist_title": "Watchlist",
        "watchlist_empty": "Watchlist is empty. Open a card and add it.",
        "watchlist_missing_table": "Watchlist table missing. Run the latest supabase_schema.sql, then reload schema.",
        "ai_explain_title": "Why this signal",
        "ai_confidence": "Confidence: {level}",
        "ai_low_confidence": "Signal hidden — data quality is too low.",
        "ai_expected_move": "Expected move",
        "ebay_sold_title": "eBay sold comps",
        "ebay_sold_caption": "Completed sales when Marketplace Insights is enabled; otherwise active listings only.",
        "ebay_sold_unavailable": "{hint}",
        "condition": "Condition",
        "grade": "Grade (optional)",
        "edit_lot": "Edit lot",
        "save_lot": "Save changes",
        "sell_lot": "Mark sold",
        "sale_price": "Sale price ({code})",
        "lot_updated": "Lot updated.",
        "lot_sold": "Lot marked as sold.",
        "open_lots": "Open lots",
        "sold_lots": "Sold lots",
        "realized_pnl": "Realized P&L",
        "kpi_realized": "Realized P&L",
        "portfolio_perf": "Portfolio value vs cost (open lots)",
        "status_open": "Open",
        "status_sold": "Sold",
        "backtest_title": "Momentum backtest (last {days}d)",
        "backtest_caption": "Cards that already rose ≥ {pct:.0f}% over the lookback — transparency check, not the live XGBoost score.",
        "backtest_hit_rate": "Positive share",
        "backtest_avg": "Avg trailing %",
        "backtest_empty": "Not enough history for a backtest on this filter.",
        "retry_live_prices": "Retry live prices",
        "retry_live_done": "Cleared live cache — reloading…",
        "obs_title": "Data health (this session)",
        "obs_caption": "JustTCG fetch outcomes while you browse. High fallback % means matching or rate limits need attention.",
        "obs_live": "Live OK",
        "obs_fallback": "DB fallback",
        "obs_empty": "Empty",
        "obs_errors": "Errors",
        "obs_cache": "Cache hits",
        "obs_miss_rate": "Miss/fallback",
        "watchlist_delta": "{pct:+.1f}% vs AI expected",
        "chart_skeleton": "Loading price history…",
        "search": "Search",
        "search_ph": "Name or ID…",
        "search_ph_name": "Name…",
        "set": "Set",
        "rarity": "Rarity",
        "signal": "Signal",
        "sort": "Sort",
        "all": "All",
        "all_sets": "All sets",
        "per_page": "Per page",
        "prev": "← Previous",
        "next": "Next →",
        "page_of": "Page {page} / {pages} · showing {start}–{end} of {total}",
        "filtered_of": "Filtered: **{n}** / {total} cards",
        "shown_of": "Showing **{n}** / {total} lots",
        "no_cards_filters": "No cards match these filters.",
        "no_cards_display": "No cards to display.",
        "no_entries_filters": "No lots match these filters.",
        "grid_cards": "Card grid",
        "detail_ai": "Detail & AI forecast",
        "pick_card_chart": "Select a card for the chart",
        "click_card_ai": "Click a card in the grid for the AI forecast and chart.",
        "show_ai": "AI detail",
        "back_explore": "← Back to Explore",
        "compare_history": "Compare price history",
        "compare_history_caption": "Compare prices from different sources. JustTCG = NM live; PSA 10 = JustTCG graded (v2); TCGplayer = saved market history.",
        "chart_range": "Range",
        "chart_range_all": "All",
        "price_source": "Price source",
        "source_label": "Source: {name}",
        "source_unavailable": "This source or exact printing is not available for this card.",
        "source_nm_usd": "Near Mint · USD · live",
        "source_nm_db_fallback": "Near Mint · saved JustTCG/market history",
        "source_market_db": "Market history (database)",
        "source_psa10_usd": "PSA 10 · USD · JustTCG graded (sales-based)",
        "source_psa10_spot_only": "PSA 10 spot (no daily series in API yet) · {period} sales={sales}",
        "justtcg_key_missing": "JUSTTCG_API_KEY is not set (Streamlit Secrets or .env). Showing saved history; live JustTCG is off.",
        "justtcg_no_product_id": "No tcgplayer_id for this card — try another card or refresh catalog sync.",
        "justtcg_fetch_error": "JustTCG error: {error}",
        "justtcg_using_saved": "JustTCG live NM history was empty for this printing — showing your saved market history instead.",
        "justtcg_tcp_column_hint": "Tip: add cards.tcgplayer_id in Supabase for more reliable JustTCG matches (SQL in schema).",
        "loading_justtcg": "Loading JustTCG history…",
        "loading_psa10": "Loading JustTCG PSA 10…",
        "psa10_unpriced": "No recorded PSA 10 sale for this card in JustTCG yet (still unpriced).",
        "psa10_fetch_error": "JustTCG PSA 10 error: {error}",
        "ebay_listings": "eBay listings",
        "ebay_listings_caption": "Live Browse listings (active). Not sold history — Insights API is separate.",
        "ebay_loading": "Loading eBay listings…",
        "ebay_key_missing": "eBay keys are not set (EBAY_APP_ID + EBAY_CERT_ID or EBAY_OAUTH_TOKEN).",
        "ebay_key_missing_hint": "Local: add to .env and restart Streamlit. Cloud: Settings → Secrets (see .streamlit/secrets.toml.example), then Reboot.",
        "ebay_no_results": "No active eBay listings for this card.",
        "ebay_fetch_error": "eBay error: {error}",
        "ebay_col_title": "Title",
        "ebay_col_price": "Price",
        "ebay_col_condition": "Condition",
        "ebay_col_link": "Link",
        "ebay_from_price": "eBay from {price} · {n} listings",
        "ai_prediction": "AI forecast",
        "price_on": "Price on {date}",
        "ai_caption": "Percent is expected next-day move. HOLD within ±{band:.2f}%, otherwise BUY or SELL.",
        "no_history_card": "No price_history rows for the selected card.",
        "short_series": "Series is shorter than 8 days, so lag features for tomorrow are not ready yet.",
        "market_title": "Market & AI",
        "cards": "Cards",
        "sort_name": "Name A–Z",
        "sort_price_desc": "Price ↓",
        "sort_price_asc": "Price ↑",
        "sort_exp_desc": "Expected % ↓",
        "sort_exp_asc": "Expected % ↑",
        "gallery_title": "Collection gallery",
        "gallery_caption": "Hover: 3D tilt · rare/TOP AI: holo-foil · click: zoom + same 3D tilt · ❌ removes lot",
        "pnl": "P&L",
        "pnl_all": "All",
        "pnl_up": "In profit",
        "pnl_down": "In loss",
        "pnl_top_ai": "TOP AI",
        "sort_value_desc": "Value ↓",
        "sort_value_asc": "Value ↑",
        "sort_pnl_desc": "P&L ↓",
        "sort_pnl_asc": "P&L ↑",
        "sort_qty_desc": "Qty ↓",
        "remove": "Remove {name}",
        "add_card": "Add card",
        "card": "Card",
        "quantity": "Quantity",
        "purchase_price": "Purchase price ({code})",
        "price_range": "Price ({code})",
        "price_min": "Min",
        "price_max": "Max",
        "yaxis_price": "Price ({code})",
        "add_to_portfolio": "Add to portfolio",
        "portfolio_empty": "Portfolio is empty. Pick a card, quantity and purchase price.",
        "added_to_portfolio": "{name} was added to the portfolio.",
        "removed_from_portfolio": "{name} was removed from the portfolio.",
        "entry_not_found": "Lot #{id} was not found.",
        "kpi_value": "Total collection value",
        "kpi_invested": "Total invested",
        "kpi_pnl": "Total P&L",
        "outlook_up": "AI expects your portfolio value to rise by {pct:.1f}% next week.",
        "outlook_down": "AI expects your portfolio value to fall by {pct:.1f}% next week.",
        "outlook_flat": "AI expects your portfolio value to stay roughly flat next week.",
        "outlook_caption": "Now {current} → {week} in {days} days. The week is seven recursive next-day XGBoost forecasts.",
        "fx_rate": "FX: 1 USD = {rate:.4f} EUR",
        "scanner_title": "🤖 AI Scanner",
        "scanner_caption": "XGBoost scan of all cards · {days}-day target from lags (yesterday, −3d, −7d, 7-day average).",
        "min_growth_top": "Min. TOP growth (%)",
        "no_scan_history": "Not enough history for an AI scan. Check price_history.",
        "scanned_filtered": "Scanned / filtered",
        "top_opps": "TOP opportunities",
        "drop_warnings": "Drop warnings",
        "top_opps_heading": "🔥 TOP AI OPPORTUNITIES (growth ≥ {pct:.0f}%)",
        "no_top_opps": "No cards with expected growth above {pct:.0f}% for this filter. Lower the threshold.",
        "drop_heading": "⚠️ AI DROP WARNINGS",
        "no_drop_warnings": "No cards with a predicted drop for this filter.",
        "table_page": "Table view for this page",
        "closing": "Last close",
        "day_change": "Day change",
        "field": "Field",
        "value": "Value",
        "qty_label": "Qty: {n}",
        "missing_supabase": "Supabase credentials are missing.",
        "no_price_history": "No price history. Check the seed DB or run generate_history.py.",
        "check_secrets": "Check Secrets and reboot the app.",
        "click_zoom": "Click to zoom",
        "image_unavailable": "image unavailable",
        "scanning": "Scanning all cards with XGBoost...",
        "change_60d": "60d change",
        "points_series": "Points in series",
        "price_yesterday": "Yesterday's price",
        "rolling_7d": "7-day average",
        "chart_close": "Close",
        "chart_ai": "AI — next day",
        "chart_price_label": "Price",
        "chart_price_latest": "Latest",
        "col_name": "Name",
        "col_current": "Current price",
        "col_ai_target": "AI target price",
        "col_roi": "Expected ROI (%)",
        "load_exchange": "Loading history and training XGBoost...",
        "chart_title": "{name} · price history",
        "xaxis_date": "Date",
        "supabase_secrets_help": """**Streamlit Cloud → ⋮ Manage app → Settings → Secrets**  
Paste this TOML (replace the values), **Save**, then **Reboot**:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SERVICE_ROLE_KEY"
```

Keys: Supabase → **Project Settings → API**  
(`Project URL` + `service_role`).

**Important:** URL must be only `https://xxxx.supabase.co` —  
**without** `/rest/v1` at the end (otherwise PGRST125).""",
        "supabase_schema_help": """### Create tables in Supabase
1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project  
2. Left: **SQL Editor** → **New query**  
3. Copy the SQL below → paste → **Run**  
4. **Table Editor**: you should see `cards`, `price_history`, `portfolio`  
5. If the app still errors: **Project Settings → API → Reload schema**  
6. Streamlit → **Reboot**""",
        "login_title": "Sign in",
        "login_caption": "Use your email and password (Supabase Auth).",
        "login_email": "Email",
        "login_password": "Password",
        "login_signin": "Sign in",
        "login_signup": "Create account",
        "login_or": "or",
        "login_success": "Signed in as {email}",
        "signup_success": "Account created. You are signed in as {email}.",
        "signup_confirm": "Account created. Check your email to confirm, then sign in.",
        "login_error": "Auth error: {error}",
        "logout": "Log out",
        "logged_in_as": "{email}",
        "portfolio_user_id_migration": "Portfolio needs a user_id column. Run this SQL in Supabase SQL Editor, then Reload schema / reboot the app.",
}

# Stable filter sentinels (language-independent).
FILTER_ALL = "__ALL__"
FILTER_ALL_SETS = "__ALL_SETS__"
PNL_ALL = "all"
PNL_UP = "up"
PNL_DOWN = "down"
PNL_TOP = "top_ai"

# Canonical trading signals (English).
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"

# Legacy Croatian codes still accepted from older session/cache values.
_SIGNAL_ALIASES = {
    "KUPI": SIGNAL_BUY,
    "PRODAJ": SIGNAL_SELL,
    "DRZI": SIGNAL_HOLD,
    "DRŽI": SIGNAL_HOLD,
    SIGNAL_BUY: SIGNAL_BUY,
    SIGNAL_SELL: SIGNAL_SELL,
    SIGNAL_HOLD: SIGNAL_HOLD,
}


def get_lang() -> str:
    return "en"


def t(key: str, **kwargs: Any) -> str:
    template = _TEXT.get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template


def signal_label(signal: str) -> str:
    return _SIGNAL_ALIASES.get(str(signal), str(signal))


def normalize_signal(signal: str) -> str:
    return _SIGNAL_ALIASES.get(str(signal), str(signal))
