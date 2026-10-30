"""TCG AI Market Dashboard — composition root."""

import importlib
import subprocess
import sys

# (import_name, pip_name) — scikit-learn imports as sklearn.
_REQUIRED_PIP = (
    ("plotly", "plotly"),
    ("xgboost", "xgboost"),
    ("sklearn", "scikit-learn"),
    ("supabase", "supabase"),
)


def _ensure_runtime_deps() -> None:
    missing: list[str] = []
    for import_name, pip_name in _REQUIRED_PIP:
        try:
            importlib.import_module(import_name)
        except ModuleNotFoundError:
            missing.append(pip_name)
    if not missing:
        return
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", *missing],
    )
    importlib.invalidate_caches()


_ensure_runtime_deps()

import streamlit as st

from currency import money

try:
    from database import user_data_client_mode
except ImportError:
    import traceback

    traceback.print_exc(file=sys.stderr)
    raise

from services.alerts import safe_collect_and_render_alerts
from services.exchange import clear_exchange_cache, load_exchange
from services.prices import justtcg_observability_summary
from ui.catalog import render_explore, render_market
from ui.nav import apply_nav_query_params, render_login_gate, render_navbar
from ui.portfolio import render_portfolio
from ui.scanner import render_scanner
from ui.styles import inject_app_styles

import i18n as _i18n_mod

importlib.reload(_i18n_mod)
from i18n import t

st.set_page_config(
    page_title="TCG AI Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def render_data_health_expander() -> None:
    with st.expander(t("obs_title"), expanded=False):
        st.caption(t("obs_caption"))
        summary = justtcg_observability_summary()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("obs_live"), int(summary.get("live", 0)))
        c2.metric(t("obs_fallback"), int(summary.get("fallback", 0)))
        c3.metric(t("obs_empty"), int(summary.get("empty", 0)))
        c4.metric(t("obs_errors"), int(summary.get("error", 0)))
        c5.metric(t("obs_miss_rate"), f"{float(summary.get('miss_or_fallback_pct', 0)):.0f}%")
        st.caption(f"{t('obs_cache')}: {int(summary.get('cache_hit', 0))}")
        if st.button(t("obs_reload_model"), key="reload_exchange_cache"):
            clear_exchange_cache()
            st.session_state["portfolio_notice"] = t("obs_reload_done")
            st.rerun()


def _current_user_id() -> str:
    import auth as auth_mod

    user = auth_mod.current_user() or {}
    return str(user.get("id") or "").strip()


def main() -> None:
    inject_app_styles()
    apply_nav_query_params()

    from config import get_supabase_credentials

    url, key = get_supabase_credentials()
    if not url or not key:
        st.error(t("missing_supabase"))
        st.markdown(t("supabase_secrets_help"))
        return

    if not render_login_gate():
        return

    page = render_navbar()

    mode = user_data_client_mode()
    if mode == "missing_anon":
        st.warning(t("auth_rls_fallback"))
    elif mode == "missing_token":
        st.warning(t("auth_session_stale"))
    elif mode == "service_fallback":
        st.warning(t("auth_rls_fallback_generic"))

    try:
        with st.spinner(t("load_exchange")):
            history, market, model = load_exchange()
    except RuntimeError as exc:
        st.error(str(exc))
        message = str(exc).lower()
        if "table" in message or "schema" in message or "cards" in message:
            from database import SCHEMA_SQL

            st.markdown(t("supabase_schema_help"))
            st.code(SCHEMA_SQL, language="sql")
        else:
            st.info(t("check_secrets"))
        return
    if market.empty or history.empty:
        st.error(t("no_price_history"))
        return

    threshold = float(st.session_state.get("watch_alert_threshold", 5.0))
    safe_collect_and_render_alerts(
        market,
        user_id=_current_user_id(),
        threshold_pct=threshold,
        money_fmt=money,
    )

    if page == "explore":
        render_explore(market, history=history, model=model)
    elif page == "market":
        render_market(history, market, model)
    elif page == "portfolio":
        render_portfolio(history, market, model)
    else:
        render_scanner(history, market, model)

    render_data_health_expander()


if __name__ == "__main__":
    main()
