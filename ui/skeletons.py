"""Loading skeleton placeholders for catalog / chart."""

from __future__ import annotations

import streamlit as st

from i18n import t

SKELETON_CSS = """
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
"""


def render_catalog_skeleton(n: int = 10) -> None:
    cards = "".join(
        '<div class="skel-card"><div class="skel-img"></div>'
        '<div class="skel-line"></div><div class="skel-line short"></div></div>'
        for _ in range(max(1, int(n)))
    )
    st.markdown(
        f"<style>{SKELETON_CSS}</style><div class='skel-grid'>{cards}</div>",
        unsafe_allow_html=True,
    )


def render_chart_skeleton() -> None:
    st.markdown(
        f"<style>{SKELETON_CSS}</style>"
        f"<div class='skel-chart'>{t('chart_skeleton')}</div>",
        unsafe_allow_html=True,
    )
