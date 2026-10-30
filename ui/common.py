"""Shared Streamlit UI helpers."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from currency import currency_code, currency_symbol, from_display, money, to_display
from i18n import FILTER_ALL, FILTER_ALL_SETS, t
from ui.tiles import market_tile_html

def chip_row(items: list[tuple[str, str]], css_class: str) -> None:
    cells = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value">{escape(value)}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="{css_class}">{cells}</div>', unsafe_allow_html=True)

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

