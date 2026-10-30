"""Plotly price chart + hover price counter."""

from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from currency import currency_symbol, money, to_display
from i18n import t
from trading_signals import trading_signal


def hex_to_rgba(color: str, alpha: float) -> str:
    raw = (color or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return f"rgba(56, 189, 248, {alpha})"
    r = int(raw[0:2], 16)
    g = int(raw[2:4], 16)
    b = int(raw[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def clip_series_range(series: pd.DataFrame, range_key: str) -> pd.DataFrame:
    if series is None or series.empty:
        return series if isinstance(series, pd.DataFrame) else pd.DataFrame(columns=["date", "price"])
    frame = series.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    end = frame["date"].max()
    days = {"1m": 30, "3m": 90}.get(range_key)
    if days is None:
        return frame.sort_values("date").reset_index(drop=True)
    start = end - pd.Timedelta(days=days)
    return frame.loc[frame["date"] >= start].sort_values("date").reset_index(drop=True)


def price_chart(
    series: pd.DataFrame,
    predicted: float | None,
    name: str,
    *,
    source_label: str | None = None,
    show_ai: bool = True,
    line_color: str = "#38bdf8",
    overlays: list[tuple[pd.DataFrame, str, str]] | None = None,
) -> go.Figure:
    """Primary series + optional overlays [(frame, label, color), ...]."""
    overlay_rows = [
        (frame, label, color)
        for frame, label, color in (overlays or [])
        if isinstance(frame, pd.DataFrame) and not frame.empty
    ]
    if series.empty and not overlay_rows:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title=name,
            height=360,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.35)",
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

    primary = series if not series.empty else overlay_rows[0][0]
    last_day = pd.Timestamp(primary["date"].iloc[-1])
    last_price = float(primary["price"].iloc[-1])
    y_hist = primary["price"].astype(float).map(to_display)
    close_label = source_label or t("chart_close")
    money_hover = f"{currency_symbol()}%{{y:.4f}}"
    fill_color = hex_to_rgba(line_color, 0.22)
    y_values = [float(y_hist.min()), float(y_hist.max())] if len(y_hist) else []
    if len(y_hist):
        band_floor = float(y_hist.min()) - max(
            (float(y_hist.max()) - float(y_hist.min())) * 0.08, 0.01
        )
    else:
        band_floor = 0.0

    fig = go.Figure()
    if not series.empty:
        fig.add_trace(
            go.Scatter(
                x=series["date"],
                y=[band_floor] * len(series),
                mode="lines",
                line=dict(width=0, color="rgba(0,0,0,0)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=series["date"],
                y=y_hist,
                mode="lines",
                name=close_label,
                line=dict(color=line_color, width=2.8, shape="linear"),
                fill="tonexty",
                fillcolor=fill_color,
                hovertemplate=f"%{{x|%d.%m.%Y}}<br>{money_hover}<extra>{close_label}</extra>",
            )
        )
    for frame, label, color in overlay_rows:
        if not series.empty and label == close_label:
            continue
        y_over = frame["price"].astype(float).map(to_display)
        y_values.extend([float(y_over.min()), float(y_over.max())])
        fig.add_trace(
            go.Scatter(
                x=frame["date"],
                y=y_over,
                mode="lines",
                name=label,
                line=dict(color=color, width=2.2, shape="linear"),
                hovertemplate=f"%{{x|%d.%m.%Y}}<br>{money_hover}<extra>{label}</extra>",
            )
        )
    if show_ai and predicted is not None and not primary.empty:
        next_day = last_day + pd.Timedelta(days=1)
        y_last = to_display(last_price)
        y_pred = to_display(predicted)
        signal = trading_signal(last_price, predicted)
        forecast_color = {"BUY": "#22c55e", "SELL": "#f87171", "HOLD": "#fbbf24"}[signal]
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

    if not y_values:
        y_values = [0.0, 1.0]
    price_low = min(y_values)
    price_high = max(y_values)
    pad = max((price_high - price_low) * 0.18, abs(price_low) * 0.01, 0.01)
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title=None,
        height=440,
        margin=dict(l=8, r=12, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,18,32,0.35)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#94a3b8"),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.94)",
            bordercolor="rgba(148, 163, 184, 0.35)",
            font=dict(size=12, color="#e2e8f0"),
        ),
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor="rgba(30, 41, 59, 0.65)",
            showgrid=True,
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikedash="dot",
            spikethickness=1,
            spikecolor="#64748b",
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(30, 41, 59, 0.65)",
            showgrid=True,
            tickprefix=currency_symbol(),
            range=[price_low - pad, price_high + pad],
            zeroline=False,
            side="right",
        ),
    )
    return fig


def render_chart_price_counter(
    price_usd: float | None,
    *,
    counter_id: str,
    accent: str = "#38bdf8",
) -> None:
    if price_usd is None:
        return
    display_value = float(to_display(price_usd))
    symbol = currency_symbol()
    digits = 4 if display_value < 10 else 2
    initial = money(price_usd, digits=digits)
    st.markdown(
        f"""
        <div class="chart-price-head" data-counter-root="{escape(counter_id, quote=True)}">
          <p class="chart-price-label">{escape(t("chart_price_label"))}</p>
          <p class="chart-price-counter" id="{escape(counter_id, quote=True)}"
             data-value="{display_value:.6f}"
             data-base="{display_value:.6f}"
             data-symbol="{escape(symbol, quote=True)}"
             data-digits="{digits}"
             style="--accent:{escape(accent, quote=True)}">{escape(initial)}</p>
          <p class="chart-price-date" id="{escape(counter_id, quote=True)}-date">{escape(t("chart_price_latest"))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_chart_hover_counter(counter_id: str) -> None:
    cid = escape(counter_id, quote=True)
    latest = t("chart_price_latest")
    components.html(
        f"""
<script>
(function () {{
  const COUNTER_ID = "{cid}";
  const doc = window.parent.document;
  const counter = doc.getElementById(COUNTER_ID);
  if (!counter) return;
  const dateEl = doc.getElementById(COUNTER_ID + "-date");
  const symbol = counter.dataset.symbol || "$";
  const digits = Number(counter.dataset.digits || "2");
  const base = Number(counter.dataset.base || "0");
  let anim = null;
  let current = Number(counter.dataset.value || base);

  function formatMoney(v) {{
    const n = Number(v);
    if (!Number.isFinite(n)) return symbol + "—";
    return symbol + n.toLocaleString(undefined, {{
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    }});
  }}

  function setDate(text) {{
    if (dateEl) dateEl.textContent = text || "";
  }}

  function animateTo(target, ms) {{
    const from = current;
    const to = Number(target);
    if (!Number.isFinite(to)) return;
    if (anim) cancelAnimationFrame(anim);
    const start = performance.now();
    const dur = Math.max(120, ms || 280);
    function frame(now) {{
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      current = from + (to - from) * eased;
      counter.dataset.value = String(current);
      counter.textContent = formatMoney(current);
      if (p < 1) anim = requestAnimationFrame(frame);
      else {{
        current = to;
        counter.dataset.value = String(to);
        counter.textContent = formatMoney(to);
        anim = null;
      }}
    }}
    anim = requestAnimationFrame(frame);
  }}

  function pickPoint(ev) {{
    const pts = (ev && ev.points) || [];
    if (!pts.length) return null;
    let pt = pts.find(p => p.curveNumber === 1) || pts.find(p => p.curveNumber === 0) || pts[0];
    const y = (pt.y != null) ? Number(pt.y) : Number(pt.customdata);
    if (!Number.isFinite(y)) return null;
    let dateTxt = "";
    if (pt.x != null) {{
      const d = new Date(pt.x);
      if (!Number.isNaN(d.getTime())) {{
        dateTxt = d.toLocaleDateString(undefined, {{ day: "2-digit", month: "short", year: "numeric" }});
      }} else {{
        dateTxt = String(pt.x);
      }}
    }}
    return {{ y, dateTxt }};
  }}

  function onHover(ev) {{
    const hit = pickPoint(ev);
    if (!hit) return;
    counter.classList.add("is-hover");
    animateTo(hit.y, 180);
    setDate(hit.dateTxt);
  }}

  function onUnhover() {{
    counter.classList.remove("is-hover");
    animateTo(base, 320);
    setDate({latest!r});
  }}

  function bindPlot(plot) {{
    if (!plot || plot.dataset.counterBound === COUNTER_ID) return;
    plot.dataset.counterBound = COUNTER_ID;
    plot.on("plotly_hover", onHover);
    plot.on("plotly_unhover", onUnhover);
  }}

  function findNearbyPlot() {{
    const root = counter.closest("[data-testid=\\"stVerticalBlock\\"]") || counter.parentElement;
    const scope = root || doc;
    const plots = scope.querySelectorAll(".js-plotly-plot");
    if (!plots.length) return null;
    let chosen = null;
    for (const p of plots) {{
      if (counter.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING) {{
        chosen = p;
        break;
      }}
    }}
    return chosen || plots[plots.length - 1];
  }}

  let tries = 0;
  function tick() {{
    const plot = findNearbyPlot();
    if (plot && plot.on) {{
      bindPlot(plot);
      return;
    }}
    if (++tries < 40) setTimeout(tick, 150);
  }}
  tick();
}})();
</script>
        """,
        height=0,
    )
