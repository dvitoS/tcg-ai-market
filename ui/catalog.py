"""Catalog browse + AI signals modes."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from currency import currency_code, from_display, money, to_display
from i18n import FILTER_ALL, FILTER_ALL_SETS, signal_label, t
from ui.common import (
    filter_market_frame,
    price_bounds,
    render_market_grid,
    render_pill_toggle,
    render_price_slider,
)
from ui.detail import render_market_detail
from ui.skeletons import render_catalog_skeleton
from ui.tiles import explore_card_html, market_tile_html


def set_nav_query_params(*, page: str, card_id: str | None = None) -> None:
    from ui.nav import set_nav_query_params as _set

    return _set(page=page, card_id=card_id)

EXPLORE_BATCH = 24

EXPLORE_INFINITE_SCROLL_JS = """
(function () {
  const doc = window.parent.document;
  if (doc.documentElement.dataset.exploreScrollBound === "1") return;
  doc.documentElement.dataset.exploreScrollBound = "1";
  let busy = false;
  function loadMoreLabel(text) {
    const t = (text || "").trim().toLowerCase();
    return t.includes("load more");
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




@st.cache_resource(show_spinner="Loading history and training XGBoost...")
def select_explore_card(card_id: str) -> None:
    """Streamlit on_click — detail-first inside Catalog."""
    st.session_state["market_selected_id"] = str(card_id)
    st.session_state["nav_page"] = "explore"
    st.session_state["market_detail_only"] = True
    set_nav_query_params(page="explore", card_id=str(card_id))

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

def render_explore(market: pd.DataFrame, history: pd.DataFrame | None = None, model=None) -> None:
    """Catalog: Browse + AI signals modes, detail-first card view."""
    selected_id = st.session_state.get("market_selected_id")
    market_ids = set(market["id"].astype(str))
    if (
        history is not None
        and model is not None
        and st.session_state.get("market_detail_only")
        and selected_id is not None
        and str(selected_id) in market_ids
    ):
        if st.button(t("back_explore"), key="catalog_back"):
            st.session_state["market_detail_only"] = False
            st.session_state.pop("market_selected_id", None)
            st.session_state.pop("_catalog_prev_pick", None)
            set_nav_query_params(page="explore")
            st.rerun()
        set_nav_query_params(page="explore", card_id=str(selected_id))
        render_market_detail(history, market, model, str(selected_id))
        return

    st.markdown('<div class="catalog-hero-search"></div>', unsafe_allow_html=True)
    mode = render_pill_toggle(
        [("browse", t("catalog_browse")), ("signals", t("catalog_signals"))],
        state_key="catalog_mode",
        default="browse",
    )

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

    if mode == "signals":
        counts = market["signal"].value_counts() if "signal" in market.columns else {}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(t("cards"), len(market))
        m2.metric(signal_label("BUY"), int(counts.get("BUY", 0)))
        m3.metric(signal_label("HOLD"), int(counts.get("HOLD", 0)))
        m4.metric(signal_label("SELL"), int(counts.get("SELL", 0)))

    sort_options = ["name", "price_desc", "price_asc", "exp_desc", "exp_asc"]
    sort_labels = {
        "name": t("sort_name"),
        "price_desc": t("sort_price_desc"),
        "price_asc": t("sort_price_asc"),
        "exp_desc": t("sort_exp_desc"),
        "exp_asc": t("sort_exp_asc"),
    }
    sort_col, signal_col = st.columns([1.4, 1.4])
    with sort_col:
        sort_by = st.selectbox(
            t("explore_sort_by"),
            sort_options,
            format_func=lambda k: sort_labels[k],
            key="explore_sort",
        )
    signal_filter = FILTER_ALL
    with signal_col:
        if mode == "signals":
            signal_options = [FILTER_ALL, "BUY", "SELL", "HOLD"]
            signal_filter = st.selectbox(
                t("signal"),
                signal_options,
                format_func=lambda s: t("all") if s == FILTER_ALL else signal_label(s),
                key="catalog_signal",
            )

    left, right = st.columns([1.05, 3.2], gap="large")
    with left:
        with st.container(border=True):
            st.markdown(
                f'<div class="explore-filter-head">'
                f"<h4>{escape(t('explore_filters'))}</h4></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="explore-filter-label">{escape(t("explore_category"))}</div>',
                unsafe_allow_html=True,
            )
            st.checkbox(
                t("explore_cat_pokemon"),
                value=True,
                disabled=True,
                key="exp_pokemon_cb",
            )
            sets = [FILTER_ALL_SETS] + sorted(market["set_name"].dropna().unique().tolist())
            set_filter = st.selectbox(
                t("set"),
                sets,
                format_func=lambda s: t("all_sets") if s == FILTER_ALL_SETS else s,
                key="catalog_set",
            )
            rarities = [FILTER_ALL] + sorted(market["rarity"].dropna().unique().tolist())
            rarity_filter = st.selectbox(
                t("rarity"),
                rarities,
                format_func=lambda r: t("all") if r == FILTER_ALL else r,
                key="catalog_rarity",
            )
            st.markdown(
                f'<div class="explore-filter-label">{escape(t("explore_price_box"))}'
                f" ({escape(currency_code())})</div>",
                unsafe_allow_html=True,
            )
            price_min, price_max = render_explore_price_box(market["price"])
            if st.button(
                t("explore_reset"),
                key="explore_reset_filters",
                use_container_width=True,
            ):
                _reset_explore_price_keys()
                st.session_state["explore_query"] = ""
                st.session_state["explore_shown"] = EXPLORE_BATCH
                st.rerun()

    filtered = filter_market_frame(
        market,
        query=query or "",
        set_name=set_filter,
        rarity=rarity_filter,
        signal=signal_filter,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max,
    )

    fingerprint = f"{mode}|{query}|{sort_by}|{signal_filter}|{set_filter}|{rarity_filter}|{price_min}|{price_max}"
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
            render_catalog_skeleton(n=8)
        else:
            if mode == "signals":
                prev_pick = st.session_state.get("_catalog_prev_pick")
                render_market_grid(page_rows, selection_key="market_selected_id", cols_per_row=5)
                picked = st.session_state.get("market_selected_id")
                # Open detail only when the user just picked a new card.
                if (
                    picked
                    and str(picked) != str(prev_pick or "")
                    and str(picked) in set(page_rows["id"].astype(str))
                ):
                    st.session_state["_catalog_prev_pick"] = str(picked)
                    st.session_state["market_detail_only"] = True
                    set_nav_query_params(page="explore", card_id=str(picked))
                    st.rerun()
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
    """Legacy Market tab → Catalog AI signals + detail."""
    st.session_state["nav_page"] = "explore"
    st.session_state["catalog_mode"] = "signals"
    set_nav_query_params(
        page="explore",
        card_id=str(st.session_state["market_selected_id"])
        if st.session_state.get("market_detail_only") and st.session_state.get("market_selected_id")
        else None,
    )
    render_explore(market, history=history, model=model)
