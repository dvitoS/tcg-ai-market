"""Portfolio gallery, lots, watchlist, performance."""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from api_client import pokemontcg_image_url
from currency import currency_code, currency_symbol, from_display, money, money_signed, to_display
from database import (
    add_portfolio_position,
    delete_portfolio_position,
    load_portfolio_lots as fetch_portfolio_lots,
    load_watchlist,
    remove_watchlist_card,
    sell_portfolio_position,
    update_portfolio_position,
)
from i18n import FILTER_ALL, PNL_ALL, PNL_DOWN, PNL_TOP, PNL_UP, t
from services.forecast import card_history, forecast_price_in_days
from trading_signals import FORECAST_DAYS, SCANNER_GROWTH_FLOOR
from ui.common import apply_price_range, render_price_slider

HOLO_RARITY_KEYWORDS = ("rare", "holo", "secret", "ultra")

def is_holo_eligible(rarity: str | None, *, is_top_ai: bool = False) -> bool:
    """Rijetke / holo karte i TOP AI prilike dobivaju holo-foil klasu."""
    if is_top_ai:
        return True
    text = str(rarity or "").lower()
    return any(keyword in text for keyword in HOLO_RARITY_KEYWORDS)

def _current_user_id() -> str:
    import auth as auth_mod

    user = auth_mod.current_user() or {}
    return str(user.get("id") or "").strip()

def load_portfolio_lots() -> pd.DataFrame:
    uid = _current_user_id()
    if not uid:
        return pd.DataFrame()
    try:
        from database import ensure_portfolio_user_id_column

        ensure_portfolio_user_id_column()
    except Exception:
        pass
    lots = fetch_portfolio_lots(user_id=uid)
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
      <button type="button" class="tcg-lb-close" aria-label="Close">✕</button>
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
    # Local import: Streamlit hot-reload can keep stale gallery fn without module-level imports.
    from ui.common import render_price_slider as _render_price_slider

    price_min, price_max = _render_price_slider("gallery_price", view[price_col])

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
                    uid = _current_user_id()
                    if uid and delete_portfolio_position(entry_id, user_id=uid):
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

def render_watchlist_section(market: pd.DataFrame) -> None:
    st.markdown(f"##### {t('watchlist_title')}")
    uid = _current_user_id()
    threshold_val = float(
        st.number_input(
            t("alert_threshold"),
            min_value=1.0,
            max_value=50.0,
            value=float(st.session_state.get("watch_alert_threshold", 5.0)),
            step=1.0,
            key="watch_alert_threshold_input",
        )
    )
    st.session_state["watch_alert_threshold"] = threshold_val
    try:
        watch = load_watchlist(user_id=uid)
    except Exception:
        st.caption(t("watchlist_missing_table"))
        return
    if watch.empty:
        st.caption(t("watchlist_empty"))
        return
    quotes = market.set_index("id") if "id" in market.columns else None
    for row in watch.itertuples(index=False):
        c1, c2, c3 = st.columns([3.2, 1.6, 1])
        with c1:
            st.markdown(f"**{escape(str(row.name or row.card_id))}** · `{escape(str(row.card_id))}`")
        with c2:
            price = row.market_price
            delta_txt = ""
            if quotes is not None and str(row.card_id) in quotes.index:
                q = quotes.loc[str(row.card_id)]
                if isinstance(q, pd.DataFrame):
                    q = q.iloc[0]
                price = q.get("price", price) if hasattr(q, "get") else getattr(q, "price", price)
                exp = None
                if hasattr(q, "get"):
                    exp = q.get("expected_change_pct")
                else:
                    exp = getattr(q, "expected_change_pct", None)
                if exp is not None and pd.notna(exp):
                    delta_txt = " · " + t("watchlist_delta", pct=float(exp))
            st.caption(
                (money(float(price)) if price is not None else "—") + delta_txt
            )
        with c3:
            if st.button(t("watchlist_remove"), key=f"wl_rm_{row.card_id}"):
                remove_watchlist_card(str(row.card_id), user_id=uid)
                st.rerun()

def _parse_lot_date(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def portfolio_timeseries(
    lots: pd.DataFrame,
    history: pd.DataFrame,
    *,
    max_days: int = 120,
) -> pd.DataFrame:
    """Daily invested cost basis vs mark-to-market value for held lots."""
    if lots is None or lots.empty or history is None or history.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist = hist.dropna(subset=["date", "card_id", "price"])
    hist["card_id"] = hist["card_id"].astype(str)
    hist["price"] = pd.to_numeric(hist["price"], errors="coerce")
    hist = hist.dropna(subset=["price"])
    if hist.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    price_wide = (
        hist.sort_values("date")
        .pivot_table(index="date", columns="card_id", values="price", aggfunc="last")
        .sort_index()
        .ffill()
    )

    lot_rows: list[dict] = []
    for row in lots.itertuples(index=False):
        start = _parse_lot_date(getattr(row, "purchase_date", None))
        if start is None:
            continue
        status = str(getattr(row, "status", "open") or "open").lower()
        end = _parse_lot_date(getattr(row, "sale_date", None)) if status == "sold" else None
        if status == "sold" and end is None:
            continue
        lot_rows.append(
            {
                "card_id": str(row.card_id),
                "qty": float(row.quantity or 0),
                "cost": float(row.purchase_price or 0),
                "start": start,
                "end": end,
            }
        )
    if not lot_rows:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    start_date = min(r["start"] for r in lot_rows)
    end_date = pd.Timestamp.today().normalize()
    # Align to available history window.
    hist_start = pd.Timestamp(price_wide.index.min()).normalize()
    hist_end = pd.Timestamp(price_wide.index.max()).normalize()
    start_date = max(start_date, hist_start)
    end_date = min(end_date, hist_end)
    if end_date < start_date:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    all_days = pd.date_range(start_date, end_date, freq="D")
    if len(all_days) > max_days:
        all_days = all_days[-max_days:]

    # Reindex prices onto daily calendar.
    price_daily = price_wide.reindex(price_wide.index.union(all_days)).sort_index().ffill()
    price_daily = price_daily.reindex(all_days)

    invested_vals: list[float] = []
    value_vals: list[float] = []
    for day in all_days:
        invested = 0.0
        value = 0.0
        for lot in lot_rows:
            if lot["start"] > day:
                continue
            if lot["end"] is not None and day > lot["end"]:
                continue
            invested += lot["qty"] * lot["cost"]
            px = price_daily.at[day, lot["card_id"]] if lot["card_id"] in price_daily.columns else np.nan
            if px is not None and not pd.isna(px):
                value += lot["qty"] * float(px)
            else:
                value += lot["qty"] * lot["cost"]
        invested_vals.append(invested)
        value_vals.append(value)

    return pd.DataFrame(
        {
            "date": all_days,
            "invested": invested_vals,
            "market_value": value_vals,
        }
    )


def render_portfolio_performance(
    view: pd.DataFrame,
    *,
    lots: pd.DataFrame | None = None,
    history: pd.DataFrame | None = None,
) -> None:
    """Time-series value vs cost, plus snapshot bars for open lots."""
    st.markdown(f"##### {t('portfolio_perf')}")

    series = portfolio_timeseries(lots if lots is not None else view, history if history is not None else pd.DataFrame())
    if not series.empty and len(series) >= 2:
        st.caption(t("portfolio_perf_time"))
        fig_ts = go.Figure()
        fig_ts.add_trace(
            go.Scatter(
                name=t("kpi_invested"),
                x=series["date"],
                y=series["invested"].map(to_display),
                mode="lines",
                line=dict(color="#64748b", width=2),
            )
        )
        fig_ts.add_trace(
            go.Scatter(
                name=t("kpi_value"),
                x=series["date"],
                y=series["market_value"].map(to_display),
                mode="lines",
                line=dict(color="#38bdf8", width=2.5),
                fill="tonexty",
                fillcolor="rgba(56,189,248,0.12)",
            )
        )
        fig_ts.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.35)",
            legend=dict(orientation="h", y=1.12),
            yaxis=dict(tickprefix=currency_symbol()),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_ts, width="stretch", config={"displayModeBar": False})

    open_view = view
    if "status" in view.columns:
        open_view = view.loc[view["status"].astype(str).str.lower() != "sold"]
    if open_view.empty:
        return
    with st.expander(t("portfolio_perf_bars"), expanded=False):
        fig = go.Figure()
        names = open_view["name"].astype(str).tolist()
        fig.add_trace(
            go.Bar(
                name=t("kpi_invested"),
                x=names,
                y=open_view["invested"].astype(float).map(to_display),
                marker_color="#64748b",
            )
        )
        fig.add_trace(
            go.Bar(
                name=t("kpi_value"),
                x=names,
                y=open_view["market_value"].astype(float).map(to_display),
                marker_color="#38bdf8",
            )
        )
        fig.update_layout(
            template="plotly_dark",
            barmode="group",
            height=320,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.35)",
            legend=dict(orientation="h", y=1.12),
            yaxis=dict(tickprefix=currency_symbol()),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

def render_portfolio(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader(t("add_card"))
    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  {money(float(row.price))}"
        for row in market.sort_values("name").itertuples(index=False)
    }
    conditions = ["NM", "LP", "MP", "HP", "DMG", "PSA 10", "PSA 9", "Other"]
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
        cond_col, grade_col = st.columns(2)
        condition = cond_col.selectbox(t("condition"), conditions, index=0)
        grade = grade_col.text_input(t("grade"), value="")
        submitted = st.form_submit_button(t("add_to_portfolio"), type="primary")

    if submitted:
        uid = _current_user_id()
        try:
            add_portfolio_position(
                str(card_id),
                int(qty),
                float(from_display(cost_display)),
                user_id=uid,
                condition=str(condition),
                grade=str(grade).strip() or None,
            )
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            message = str(exc)
            if "user_id" in message.lower():
                st.error(t("portfolio_user_id_migration"))
                st.code(
                    "alter table public.portfolio "
                    "add column if not exists user_id uuid "
                    "references auth.users (id) on delete cascade;\n"
                    "create index if not exists portfolio_user_id_idx "
                    "on public.portfolio (user_id);\n"
                    "notify pgrst, 'reload schema';",
                    language="sql",
                )
            else:
                st.error(message[:220])
        else:
            name = str(market.loc[market["id"] == card_id, "name"].iloc[0])
            st.session_state["portfolio_notice"] = t("added_to_portfolio", name=name)
            st.rerun()

    notice = st.session_state.pop("portfolio_notice", None)
    if notice:
        st.success(notice)

    render_watchlist_section(market)

    try:
        lots = load_portfolio_lots()
    except Exception as exc:
        message = str(exc)
        if "user_id" in message.lower():
            st.error(t("portfolio_user_id_migration"))
            st.code(
                "alter table public.portfolio "
                "add column if not exists user_id uuid "
                "references auth.users (id) on delete cascade;\n"
                "create index if not exists portfolio_user_id_idx "
                "on public.portfolio (user_id);\n"
                "notify pgrst, 'reload schema';",
                language="sql",
            )
            return
        raise
    if lots.empty:
        render_portfolio_kpis(0.0, 0.0, 0.0, 0.0)
        st.info(t("portfolio_empty"))
        return

    if "status" not in lots.columns:
        lots["status"] = "open"
    open_lots = lots.loc[lots["status"].astype(str).str.lower() != "sold"].copy()
    sold_lots = lots.loc[lots["status"].astype(str).str.lower() == "sold"].copy()

    view = portfolio_view(open_lots if not open_lots.empty else lots.iloc[0:0], market, history, model)
    value = float(view["market_value"].sum()) if not view.empty else 0.0
    invested = float(view["invested"].sum()) if not view.empty else 0.0
    pnl = float(view["pnl"].sum()) if not view.empty else 0.0
    pnl_pct = pnl / invested * 100.0 if invested else 0.0
    realized = 0.0
    if not sold_lots.empty:
        for row in sold_lots.itertuples(index=False):
            sale = float(row.sale_price or 0.0)
            cost = float(row.purchase_price or 0.0) * float(row.quantity or 0)
            realized += sale * float(row.quantity or 0) - cost
    render_portfolio_kpis(value, invested, pnl, pnl_pct)
    st.markdown(
        f'<div class="chip"><div class="chip-label">{escape(t("kpi_realized"))}</div>'
        f'<div class="chip-value {"pnl-up" if realized >= 0 else "pnl-down"}">'
        f"{escape(money_signed(realized))}</div></div>",
        unsafe_allow_html=True,
    )
    if not view.empty:
        render_week_outlook(value, float(view["week_value"].sum()))
        render_portfolio_performance(view, lots=lots, history=history)
        render_portfolio_gallery(view)

    # Edit / sell open lots
    if not open_lots.empty:
        st.markdown(f"##### {t('edit_lot')}")
        lot_labels = {
            int(r.id): f"#{r.id} · {r.name} · qty {r.quantity} · {r.condition or 'NM'}"
            for r in open_lots.itertuples(index=False)
        }
        edit_id = st.selectbox(
            t("card"),
            options=list(lot_labels.keys()),
            format_func=lambda i: lot_labels[i],
            key="edit_lot_pick",
        )
        row = open_lots.loc[open_lots["id"] == edit_id].iloc[0]
        uid = _current_user_id()
        with st.form("edit_portfolio_lot"):
            e1, e2, e3 = st.columns(3)
            new_qty = e1.number_input(t("quantity"), min_value=1, value=int(row["quantity"]))
            new_cost = e2.number_input(
                t("purchase_price", code=currency_code()),
                min_value=0.0001,
                value=float(to_display(float(row["purchase_price"]))),
                format="%.4f",
            )
            new_cond = e3.selectbox(
                t("condition"),
                conditions,
                index=conditions.index(str(row.get("condition") or "NM"))
                if str(row.get("condition") or "NM") in conditions
                else 0,
            )
            save = st.form_submit_button(t("save_lot"))
        if save:
            try:
                update_portfolio_position(
                    int(edit_id),
                    user_id=uid,
                    quantity=int(new_qty),
                    purchase_price=float(from_display(new_cost)),
                    condition=str(new_cond),
                )
                st.session_state["portfolio_notice"] = t("lot_updated")
                st.rerun()
            except Exception as exc:
                st.warning(str(exc)[:200])
        with st.form("sell_portfolio_lot"):
            sell_price = st.number_input(
                t("sale_price", code=currency_code()),
                min_value=0.0001,
                value=float(to_display(float(row.get("market_price") or row["purchase_price"]))),
                format="%.4f",
            )
            sell = st.form_submit_button(t("sell_lot"))
        if sell:
            try:
                sell_portfolio_position(
                    int(edit_id),
                    user_id=uid,
                    sale_price=float(from_display(sell_price)),
                )
                st.session_state["portfolio_notice"] = t("lot_sold")
                st.rerun()
            except Exception as exc:
                st.warning(str(exc)[:200])

    if not sold_lots.empty:
        st.markdown(f"##### {t('sold_lots')}")
        st.dataframe(
            sold_lots[
                [
                    c
                    for c in [
                        "name",
                        "quantity",
                        "purchase_price",
                        "sale_price",
                        "sale_date",
                        "condition",
                    ]
                    if c in sold_lots.columns
                ]
            ],
            hide_index=True,
            width="stretch",
        )

