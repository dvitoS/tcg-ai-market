"""Global Streamlit CSS tokens and layout."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_CSS_PATH = Path(__file__).with_name("app.css")

# Streamlit Cloud injects "Manage app" in the parent frame — CSS inside the
# app iframe often misses it. Best-effort hide via parent/top document.
_HIDE_MANAGE_APP_JS = """
<script>
(function () {
  const SEL = [
    '[data-testid="manage-app-button"]',
    'button[kind="header"]',
    'a[href*="share.streamlit.io"]',
    'a[href*="streamlit.io/cloud"]',
  ].join(',');
  function hideIn(doc) {
    if (!doc) return;
    try {
      doc.querySelectorAll(SEL).forEach(function (el) {
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
        el.style.setProperty('pointer-events', 'none', 'important');
      });
      doc.querySelectorAll('button, a, div').forEach(function (el) {
        const t = (el.textContent || '').trim().toLowerCase();
        if (t === 'manage app' || t.indexOf('manage app') === 0) {
          el.style.setProperty('display', 'none', 'important');
          el.style.setProperty('visibility', 'hidden', 'important');
        }
      });
    } catch (e) { /* cross-origin */ }
  }
  function sweep() {
    hideIn(document);
    try { hideIn(window.parent && window.parent.document); } catch (e) {}
    try { hideIn(window.top && window.top.document); } catch (e) {}
  }
  sweep();
  setTimeout(sweep, 200);
  setTimeout(sweep, 800);
  setTimeout(sweep, 2000);
})();
</script>
"""


def inject_app_styles() -> None:
    css = _CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
    # Tiny iframe — runs JS that reaches parent when same-origin (Cloud).
    components.html(_HIDE_MANAGE_APP_JS, height=0, width=0)
