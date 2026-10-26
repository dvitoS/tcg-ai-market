"""Jednostavan HR/EN prijevod za Streamlit UI."""

from __future__ import annotations

from typing import Any

import streamlit as st

LANG_HR = "hr"
LANG_EN = "en"

_TEXT: dict[str, dict[str, str]] = {
    LANG_HR: {
        "lang_hr": "HR",
        "lang_en": "EN",
        "app_title": "📈 TCG AI Market Dashboard",
        "app_caption": "Pokémon TCG burza · portfelj · XGBoost predikcija",
        "tab_market": "Tržište & AI",
        "tab_portfolio": "Moj Portfelj",
        "tab_scanner": "🤖 AI Scanner",
        "search": "Pretraži",
        "search_ph": "Ime ili ID…",
        "search_ph_name": "Ime…",
        "set": "Set",
        "rarity": "Rijetkost",
        "signal": "Signal",
        "sort": "Sortiraj",
        "all": "Sve",
        "all_sets": "Svi setovi",
        "per_page": "Po stranici",
        "prev": "← Prethodna",
        "next": "Sljedeća →",
        "page_of": "Stranica {page} / {pages} · prikaz {start}–{end} od {total}",
        "filtered_of": "Filtrirano: **{n}** / {total} karata",
        "shown_of": "Prikazano **{n}** / {total} unosa",
        "no_cards_filters": "Nema karata za odabrane filtere.",
        "no_cards_display": "Nema karata za prikaz.",
        "no_entries_filters": "Nema unosa za odabrane filtere.",
        "grid_cards": "Grid karata",
        "detail_ai": "Detalj i AI predikcija",
        "pick_card_chart": "Odaberi kartu za graf",
        "ai_prediction": "AI predikcija (XGBoost)",
        "price_on": "Cijena {date}",
        "ai_caption": "Postotak je očekivana promjena cijene sutra. DRŽI unutar ±{band:.2f}%, inače KUPI ili PRODAJ.",
        "no_history_card": "Za odabranu kartu nema redaka u price_history.",
        "short_series": "Niz je kraći od 8 dana, pa lagovi za sutrašnju prognozu još nisu dostupni.",
        "market_title": "Tržište & AI",
        "cards": "Karata",
        "sort_name": "Ime A–Z",
        "sort_price_desc": "Cijena ↓",
        "sort_price_asc": "Cijena ↑",
        "sort_exp_desc": "Očekivano % ↓",
        "sort_exp_asc": "Očekivano % ↑",
        "gallery_title": "Galerija kolekcije",
        "gallery_caption": "Hover: 3D nagib · rijetke/TOP AI: holo-foil · klik: uvećanje + isti 3D nagib · ❌ uklanja unos",
        "pnl": "P&L",
        "pnl_all": "Sve",
        "pnl_up": "U plusu",
        "pnl_down": "U minusu",
        "pnl_top_ai": "TOP AI",
        "sort_value_desc": "Vrijednost ↓",
        "sort_value_asc": "Vrijednost ↑",
        "sort_pnl_desc": "P&L ↓",
        "sort_pnl_asc": "P&L ↑",
        "sort_qty_desc": "Količina ↓",
        "remove": "Ukloni {name}",
        "add_card": "Dodaj kartu",
        "card": "Karta",
        "quantity": "Količina",
        "purchase_price": "Nabavna cijena ({code})",
        "price_range": "Cijena ({code})",
        "price_min": "Min",
        "price_max": "Max",
        "yaxis_price": "Cijena ({code})",
        "add_to_portfolio": "Dodaj u portfelj",
        "portfolio_empty": "Portfelj je prazan. Odaberi kartu, količinu i nabavnu cijenu.",
        "added_to_portfolio": "{name} je dodan u portfelj.",
        "removed_from_portfolio": "{name} je uklonjen iz portfelja.",
        "entry_not_found": "Unos #{id} nije pronađen.",
        "kpi_value": "Ukupna vrijednost kolekcije",
        "kpi_invested": "Ukupno uloženo",
        "kpi_pnl": "Ukupni P&L",
        "outlook_up": "AI predviđa da će vrijednost vašeg portfelja idući tjedan porasti za {pct:.1f}%.",
        "outlook_down": "AI predviđa da će vrijednost vašeg portfelja idući tjedan pasti za {pct:.1f}%.",
        "outlook_flat": "AI predviđa da će vrijednost vašeg portfelja idući tjedan ostati približno ista.",
        "outlook_caption": "Sada {current} → {week} za {days} dana. Tjedan je sedam uzastopnih prognoza sljedećeg dana istim XGBoost modelom.",
        "fx_rate": "Tečaj: 1 USD = {rate:.4f} EUR",
        "scanner_title": "🤖 AI Scanner",
        "scanner_caption": "XGBoost pregled svih karata · cilj za {days} dana iz lagova (jučer, −3d, −7d, 7-dnevni prosjek).",
        "min_growth_top": "Min. rast TOP (%)",
        "no_scan_history": "Nema dovoljno povijesti za AI sken. Provjeri price_history.",
        "scanned_filtered": "Skenirano / filtrirano",
        "top_opps": "TOP prilike",
        "drop_warnings": "Upozorenja za pad",
        "top_opps_heading": "🔥 TOP AI PRILIKE (rast ≥ {pct:.0f}%)",
        "no_top_opps": "Nema karata s očekivanim rastom iznad {pct:.0f}% za odabrani filter. Spusti prag.",
        "drop_heading": "⚠️ AI UPOZORENJA ZA PAD",
        "no_drop_warnings": "Nema karata s predviđenim padom za odabrani filter.",
        "table_page": "Tablični pregled ove stranice",
        "closing": "Zadnje zatvaranje",
        "day_change": "Dnevna promjena",
        "field": "Polje",
        "value": "Vrijednost",
        "qty_label": "Količina: {n}",
        "missing_supabase": "Nedostaju Supabase credentials.",
        "no_price_history": "Nema povijesti cijena. Provjeri seed bazu ili pokreni generate_history.py.",
        "check_secrets": "Provjeri Secrets i Reboot app.",
        "click_zoom": "Klikni za uvećanje",
        "image_unavailable": "slika nedostupna",
        "scanning": "Skeniram sve karte XGBoost modelom...",
        "change_60d": "Promjena 60d",
        "points_series": "Točaka u nizu",
        "price_yesterday": "Cijena jučer",
        "rolling_7d": "7-dnevni prosjek",
        "chart_close": "Zatvaranje",
        "chart_ai": "AI — sljedeći dan",
        "col_name": "Naziv",
        "col_current": "Trenutna cijena",
        "col_ai_target": "AI Ciljna cijena",
        "col_roi": "Očekivani ROI (%)",
        "load_exchange": "Učitavam povijest i treniram XGBoost...",
        "chart_title": "{name} · povijest cijene",
        "xaxis_date": "Datum",
    },
    LANG_EN: {
        "lang_hr": "HR",
        "lang_en": "EN",
        "app_title": "📈 TCG AI Market Dashboard",
        "app_caption": "Pokémon TCG market · portfolio · XGBoost forecasts",
        "tab_market": "Market & AI",
        "tab_portfolio": "My Portfolio",
        "tab_scanner": "🤖 AI Scanner",
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
        "ai_prediction": "AI forecast (XGBoost)",
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
        "col_name": "Name",
        "col_current": "Current price",
        "col_ai_target": "AI target price",
        "col_roi": "Expected ROI (%)",
        "load_exchange": "Loading history and training XGBoost...",
        "chart_title": "{name} · price history",
        "xaxis_date": "Date",
    },
}

# Stabilni sentineli za filtere (ne ovise o jeziku).
FILTER_ALL = "__ALL__"
FILTER_ALL_SETS = "__ALL_SETS__"
PNL_ALL = "all"
PNL_UP = "up"
PNL_DOWN = "down"
PNL_TOP = "top_ai"

_LANG_WIDGET_KEYS = (
    "market_sort",
    "market_signal",
    "market_set",
    "market_rarity",
    "gallery_sort",
    "gallery_pnl",
    "gallery_rarity",
    "scanner_set",
    "scanner_rarity",
)

# Signali ostaju KUPI/PRODAJ/DRŽI u podacima; UI labela po jeziku.
SIGNAL_LABELS = {
    LANG_HR: {"KUPI": "KUPI", "PRODAJ": "PRODAJ", "DRŽI": "DRŽI"},
    LANG_EN: {"KUPI": "BUY", "PRODAJ": "SELL", "DRŽI": "HOLD"},
}


def get_lang() -> str:
    lang = st.session_state.get("lang", LANG_HR)
    return lang if lang in _TEXT else LANG_HR


def t(key: str, **kwargs: Any) -> str:
    lang = get_lang()
    template = _TEXT.get(lang, _TEXT[LANG_HR]).get(key) or _TEXT[LANG_HR].get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template


def signal_label(signal: str) -> str:
    return SIGNAL_LABELS.get(get_lang(), SIGNAL_LABELS[LANG_HR]).get(signal, signal)


def _set_lang(lang: str) -> None:
    st.session_state["lang"] = lang
    for key in _LANG_WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.rerun()


def render_language_toggle_buttons() -> None:
    """Samo HR | EN gumbi (bez vanjskog layouta)."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = LANG_HR
    current = get_lang()
    c_hr, c_en = st.columns(2)
    with c_hr:
        if st.button(
            "HR",
            key="lang_hr_btn",
            type="primary" if current == LANG_HR else "secondary",
            use_container_width=True,
        ):
            if current != LANG_HR:
                _set_lang(LANG_HR)
    with c_en:
        if st.button(
            "EN",
            key="lang_en_btn",
            type="primary" if current == LANG_EN else "secondary",
            use_container_width=True,
        ):
            if current != LANG_EN:
                _set_lang(LANG_EN)


def render_language_toggle() -> None:
    """Gumb HR | EN u gornjem desnom kutu."""
    _, box = st.columns([5.2, 1.0])
    with box:
        render_language_toggle_buttons()
