"""USD / EUR prikaz cijena. Podaci u bazi ostaju u USD."""

from __future__ import annotations

import requests
import streamlit as st

CURRENCY_USD = "usd"
CURRENCY_EUR = "eur"

# Fallback ako API nije dostupan.
_FALLBACK_USD_EUR = 0.92

_CURRENCY_WIDGET_PREFIXES = (
    "market_price",
    "gallery_price",
    "scanner_price",
    "explore_price",
)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_usd_eur_rate() -> float:
    """Frankfurter (ECB) — bez API keya. Cache 6 h."""
    try:
        response = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD", "to": "EUR"},
            timeout=8,
        )
        response.raise_for_status()
        rate = float(response.json()["rates"]["EUR"])
        if rate > 0:
            return rate
    except Exception:
        pass
    return _FALLBACK_USD_EUR


def get_currency() -> str:
    cur = st.session_state.get("currency", CURRENCY_USD)
    return cur if cur in {CURRENCY_USD, CURRENCY_EUR} else CURRENCY_USD


def usd_to_eur_rate() -> float:
    return float(fetch_usd_eur_rate())


def to_display(amount_usd: float | None) -> float:
    if amount_usd is None:
        return 0.0
    value = float(amount_usd)
    if get_currency() == CURRENCY_EUR:
        return value * usd_to_eur_rate()
    return value


def from_display(amount: float | None) -> float:
    """Vraća USD iz iznosa u trenutnoj display valuti (za filtere / unos)."""
    if amount is None:
        return 0.0
    value = float(amount)
    if get_currency() == CURRENCY_EUR:
        rate = usd_to_eur_rate()
        return value / rate if rate else value
    return value


def currency_code() -> str:
    return "EUR" if get_currency() == CURRENCY_EUR else "USD"


def currency_symbol() -> str:
    return "€" if get_currency() == CURRENCY_EUR else "$"


def money(amount_usd: float | None, *, digits: int = 2) -> str:
    """Formatira USD iznos u aktivnoj valuti."""
    value = to_display(amount_usd)
    symbol = currency_symbol()
    return f"{symbol}{value:.{digits}f}"


def money_signed(amount_usd: float | None, *, digits: int = 2) -> str:
    value = to_display(amount_usd)
    sign = "+" if value > 0 else "-" if value < 0 else ""
    symbol = currency_symbol()
    return f"{sign}{symbol}{abs(value):.{digits}f}"


def money_delta(amount_usd: float | None, *, digits: int = 4) -> str:
    value = to_display(amount_usd)
    return f"{value:+.{digits}f} {currency_code()}"


def number_format_pattern(*, digits: int = 2) -> str:
    """Streamlit NumberColumn / slider format."""
    symbol = currency_symbol()
    return f"{symbol}%.{digits}f"


def _clear_price_filter_state() -> None:
    suffixes = ("", "_lo", "_hi", "_slider")
    for prefix in _CURRENCY_WIDGET_PREFIXES:
        for suffix in suffixes:
            st.session_state.pop(f"{prefix}{suffix}", None)


def _set_currency(currency: str) -> None:
    st.session_state["currency"] = currency
    _clear_price_filter_state()
    st.rerun()


def render_currency_toggle() -> None:
    """Gumbi USD | EUR."""
    if "currency" not in st.session_state:
        st.session_state["currency"] = CURRENCY_USD

    current = get_currency()
    c_usd, c_eur = st.columns(2)
    with c_usd:
        if st.button(
            "USD",
            key="cur_usd_btn",
            type="primary" if current == CURRENCY_USD else "secondary",
            use_container_width=True,
            help=f"1 USD = {usd_to_eur_rate():.4f} EUR",
        ):
            if current != CURRENCY_USD:
                _set_currency(CURRENCY_USD)
    with c_eur:
        if st.button(
            "EUR",
            key="cur_eur_btn",
            type="primary" if current == CURRENCY_EUR else "secondary",
            use_container_width=True,
            help=f"1 USD = {usd_to_eur_rate():.4f} EUR",
        ):
            if current != CURRENCY_EUR:
                _set_currency(CURRENCY_EUR)


def render_currency_bar() -> None:
    """USD|EUR + tečaj ispod naslova (ne uz jezik)."""
    from i18n import t

    if "currency" not in st.session_state:
        st.session_state["currency"] = CURRENCY_USD

    left, mid, _ = st.columns([1.1, 2.4, 4.5])
    with left:
        render_currency_toggle()
    with mid:
        st.caption(t("fx_rate", rate=usd_to_eur_rate()))
