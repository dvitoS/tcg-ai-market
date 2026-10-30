"""Navbar, auth gate, URL deep-links."""

from __future__ import annotations

from html import escape

import streamlit as st

from currency import CURRENCY_EUR, CURRENCY_USD, _set_currency, get_currency
from i18n import signal_label, t

def _query_param_value(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return str(raw[0]) if raw else None
    text = str(raw).strip()
    return text or None

def set_nav_query_params(*, page: str, card_id: str | None = None) -> None:
    """Drži deep-link u URL-u da refresh ne vrati na Explore."""
    desired: dict[str, str] = {"nav": str(page)}
    if card_id:
        desired["card"] = str(card_id)
    current_nav = _query_param_value(st.query_params.get("nav"))
    current_card = _query_param_value(st.query_params.get("card"))
    if current_nav == desired.get("nav") and current_card == desired.get("card"):
        return
    if current_nav == desired.get("nav") and desired.get("card") is None and current_card is None:
        return
    st.query_params.from_dict(desired)

def apply_nav_query_params() -> None:
    """Deep-link: ?nav=explore&card=sv3-123 (ostaje u URL-u nakon loada)."""
    card = _query_param_value(st.query_params.get("card"))
    nav = _query_param_value(st.query_params.get("nav"))
    if card is None and nav is None:
        return
    if nav == "market":
        # Legacy Market URL → Catalog (browse/signals merged).
        nav = "explore"
        if st.session_state.get("catalog_mode") is None:
            st.session_state["catalog_mode"] = "signals"
    if card is not None:
        st.session_state["market_selected_id"] = card
        st.session_state["market_detail_only"] = True
        st.session_state["nav_page"] = nav or "explore"
    elif nav is not None:
        st.session_state["nav_page"] = nav

def render_login_gate() -> bool:
    """Email/password form. Returns True when the user is authenticated."""
    import auth as auth_mod

    if auth_mod.is_authenticated():
        return True

    from config import _clean_secret_value, _secret

    if not _clean_secret_value(_secret("SUPABASE_ANON_KEY")):
        st.info(t("auth_anon_hint"))

    st.markdown(
        f"""
        <div class="compare-head" style="max-width:420px;margin:2.5rem auto 1rem;">
          <h3>{escape(t("login_title"))}</h3>
          <p class="compare-caption">{escape(t("login_caption"))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, form_col, right = st.columns([1, 1.2, 1])
    with form_col:
        email = st.text_input(t("login_email"), key="auth_email")
        password = st.text_input(
            t("login_password"),
            type="password",
            key="auth_password",
        )
        c1, c2 = st.columns(2)
        with c1:
            do_signin = st.button(
                t("login_signin"),
                type="primary",
                use_container_width=True,
                key="auth_signin_btn",
            )
        with c2:
            do_signup = st.button(
                t("login_signup"),
                use_container_width=True,
                key="auth_signup_btn",
            )
        if do_signin:
            try:
                user = auth_mod.sign_in(email, password)
                st.success(t("login_success", email=user.get("email") or email))
                st.rerun()
            except Exception as exc:
                st.error(t("login_error", error=str(exc)[:220]))
        if do_signup:
            try:
                user = auth_mod.sign_up(email, password)
                if user.get("needs_confirmation"):
                    st.info(t("signup_confirm"))
                else:
                    st.success(t("signup_success", email=user.get("email") or email))
                    st.rerun()
            except Exception as exc:
                st.error(t("login_error", error=str(exc)[:220]))
    return False

def render_navbar() -> str:
    """Collectr-style sticky header: brand | text links | currency | logout."""
    from currency import CURRENCY_EUR, CURRENCY_USD, get_currency, _set_currency
    import auth as auth_mod

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "explore"
    st.session_state.pop("nav_menu_open", None)
    # Drop leftover language / legacy signal filter state from older builds.
    st.session_state.pop("lang", None)
    if st.session_state.get("market_signal") in {"KUPI", "PRODAJ", "DRŽI", "DRZI"}:
        st.session_state["market_signal"] = signal_label(st.session_state["market_signal"])

    pages = [
        ("explore", t("nav_explore")),
        ("portfolio", t("nav_portfolio")),
        ("scanner", t("nav_scanner")),
    ]

    cur = get_currency()
    code = "USD" if cur == CURRENCY_USD else "EUR"
    user = auth_mod.current_user() or {}
    email = str(user.get("email") or "")

    # brand | 3 links | spacer | email | currency | logout
    brand, *nav_cols, _gap, email_col, cur_btn, logout_btn = st.columns(
        [1.35, 0.9, 0.9, 1.0, 2.2, 1.4, 0.65, 0.85],
        vertical_alignment="center",
        gap="medium",
    )
    with brand:
        st.markdown(
            f'<div class="nav-brand-left">TCG AI'
            f'<span>{escape(t("brand_tagline"))}</span></div>',
            unsafe_allow_html=True,
        )
    for col, (key, label) in zip(nav_cols, pages, strict=True):
        with col:
            active = st.session_state["nav_page"] == key
            if st.button(
                label,
                key=f"nav_{key}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if st.session_state["nav_page"] != key:
                    st.session_state["nav_page"] = key
                    if key != "market":
                        st.session_state["market_detail_only"] = False
                    set_nav_query_params(page=key)
                    st.rerun()
    with email_col:
        if email:
            st.caption(t("logged_in_as", email=email))
    with cur_btn:
        if st.button(
            code,
            key="nav_currency_pill",
            use_container_width=True,
            help="USD / EUR",
        ):
            _set_currency(CURRENCY_EUR if cur == CURRENCY_USD else CURRENCY_USD)
    with logout_btn:
        if st.button(t("logout"), key="nav_logout", use_container_width=True):
            auth_mod.sign_out()
            st.rerun()

    return str(st.session_state["nav_page"])

