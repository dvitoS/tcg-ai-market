"""Kestrel — composition root."""

import importlib
import sys

# Fail fast with a clear message — do not pip-install at runtime on Cloud.
_REQUIRED_PIP = (
    ("plotly", "plotly"),
    ("xgboost", "xgboost"),
    ("sklearn", "scikit-learn"),
    ("supabase", "supabase"),
    ("joblib", "joblib"),
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
    raise ImportError(
        "Missing packages: "
        + ", ".join(missing)
        + ". Install with: pip install -r requirements.txt "
        + "(Streamlit Cloud installs this automatically on reboot)."
    )


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
from ui.dealer import render_dealer_desk
from ui.nav import (
    apply_nav_query_params,
    bootstrap_session,
    is_logged_in,
    render_login_form,
    render_navbar,
)
from ui.portfolio import render_portfolio
from ui.scanner import render_scanner
from ui.styles import inject_app_styles

import i18n as _i18n_mod

importlib.reload(_i18n_mod)
from i18n import t

st.set_page_config(
    page_title="Kestrel",
    page_icon="🦅",
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

    bootstrap_session()
    page = render_navbar()

    from config import auth_disabled

    # Dedicated login page (guests). Authenticated users see catalog instead.
    if page == "login":
        if is_logged_in() and not auth_disabled():
            st.session_state["nav_page"] = "explore"
            st.rerun()
        render_login_form(reason=t("login_caption_public"))
        return

    if is_logged_in() and not auth_disabled():
        mode = user_data_client_mode()
        if mode == "missing_anon":
            st.error(t("auth_rls_blocked_anon"))
        elif mode == "missing_token":
            st.error(t("auth_session_stale"))
        elif mode == "jwt_failed":
            st.error(t("auth_rls_blocked_jwt"))
            try:
                from database_clients import last_user_supabase_error

                detail = last_user_supabase_error()
                if detail:
                    st.caption(t("auth_rls_blocked_jwt_detail", error=detail))
            except Exception:
                pass
            st.caption(t("auth_rls_fix_session_hint"))
            if st.button(t("auth_fix_session"), key="fix_jwt_session"):
                import auth as auth_mod

                auth_mod.sign_out()
                auth_mod.persist_cookies_now()
                st.rerun()

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

    if is_logged_in():
        threshold = float(st.session_state.get("watch_alert_threshold", 5.0))
        from services.pro import is_pro_user

        # Sure-only banners are a Pro surface; free users still get threshold alerts.
        sure_only = bool(st.session_state.get("watch_alert_sure_only", True)) and is_pro_user()
        safe_collect_and_render_alerts(
            market,
            user_id=_current_user_id(),
            threshold_pct=threshold,
            money_fmt=money,
            sure_only=sure_only,
        )

    if page == "explore":
        render_explore(market, history=history, model=model)
    elif page == "market":
        render_market(history, market, model)
    elif page == "portfolio":
        if not is_logged_in():
            render_login_form(reason=t("login_required_portfolio"))
        else:
            render_portfolio(history, market, model)
    elif page == "dealer":
        render_dealer_desk(market)
    else:
        render_scanner(history, market, model)

    render_data_health_expander()


if __name__ == "__main__":
    main()
