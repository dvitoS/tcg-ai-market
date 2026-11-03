"""Navbar, auth gate, URL deep-links."""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import streamlit as st

from currency import CURRENCY_EUR, CURRENCY_USD, _set_currency, get_currency
from i18n import signal_label, t

_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "kestrel-logo.png"


def logo_path() -> Path:
    return _LOGO_PATH


def _brand_logo_data_uri() -> str | None:
    if not _LOGO_PATH.is_file():
        return None
    raw = _LOGO_PATH.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _query_param_value(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return str(raw[0]) if raw else None
    text = str(raw).strip()
    return text or None

def set_nav_query_params(*, page: str, card_id: str | None = None) -> None:
    """Keep deep-link + auth sid in the URL — but stay minimal.

    - Default page ``explore`` omits ``nav`` (cleaner share URL).
    - ``sid`` stays when logged in (Streamlit Cloud session restore).
    - ``card`` only when a detail deep-link is active.
    """
    desired: dict[str, str] = {}
    page_key = str(page or "explore")
    # explore is the default home — don't pollute the URL with nav=explore.
    if page_key not in {"explore", "market"}:
        desired["nav"] = page_key
    if card_id:
        desired["card"] = str(card_id)
    sid = _query_param_value(st.query_params.get("sid"))
    if sid:
        desired["sid"] = sid

    current = {
        k: _query_param_value(st.query_params.get(k))
        for k in ("nav", "card", "sid")
    }
    desired_cmp = {
        "nav": desired.get("nav"),
        "card": desired.get("card"),
        "sid": desired.get("sid"),
    }
    if current == desired_cmp:
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


def bootstrap_session() -> None:
    """Restore JWT / DEV user; never blocks the page."""
    import auth as auth_mod

    auth_mod.bootstrap_auth()


def is_logged_in() -> bool:
    import auth as auth_mod
    from config import auth_disabled

    if auth_disabled():
        return True
    return bool(auth_mod.is_authenticated())


def render_login_form(*, reason: str | None = None) -> None:
    """Email/password form (used as dedicated page or portfolio gate)."""
    import auth as auth_mod
    from config import _clean_secret_value, _secret, auth_disabled

    if auth_disabled():
        st.info(t("auth_dev_mode"))
        return

    if not _clean_secret_value(_secret("SUPABASE_ANON_KEY")):
        st.info(t("auth_anon_hint"))

    caption = reason or t("login_caption")
    st.markdown(
        f"""
        <div class="compare-head" style="max-width:420px;margin:2.5rem auto 1rem;">
          <h3>{escape(t("login_title"))}</h3>
          <p class="compare-caption">{escape(caption)}</p>
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
                auth_mod.persist_cookies_now()
                st.success(t("login_success", email=user.get("email") or email))
                # After login, leave the login page.
                if st.session_state.get("nav_page") == "login":
                    st.session_state["nav_page"] = "explore"
                    set_nav_query_params(page="explore")
                st.rerun()
            except Exception as exc:
                st.error(t("login_error", error=str(exc)[:220]))
        if do_signup:
            try:
                user = auth_mod.sign_up(email, password)
                if user.get("needs_confirmation"):
                    st.info(t("signup_confirm"))
                else:
                    auth_mod.persist_cookies_now()
                    st.success(t("signup_success", email=user.get("email") or email))
                    if st.session_state.get("nav_page") == "login":
                        st.session_state["nav_page"] = "explore"
                        set_nav_query_params(page="explore")
                    st.rerun()
            except Exception as exc:
                st.error(t("login_error", error=str(exc)[:220]))


def render_login_gate() -> bool:
    """Back-compat: bootstrap only; browsing is public. Always returns True."""
    bootstrap_session()
    return True


def render_navbar() -> str:
    """Collectr-style sticky header: brand | text links | currency | login/logout."""
    import auth as auth_mod
    from config import auth_disabled

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
        ("dealer", t("nav_dealer")),
    ]

    cur = get_currency()
    code = "USD" if cur == CURRENCY_USD else "EUR"
    user = auth_mod.current_user() or {}
    email = str(user.get("email") or "")
    logged_in = is_logged_in()

    # brand | 4 links | spacer | email | currency | auth
    brand, *nav_cols, _gap, email_col, cur_btn, auth_btn = st.columns(
        [1.2, 0.85, 0.85, 0.85, 0.85, 1.6, 1.2, 0.6, 0.8],
        vertical_alignment="center",
        gap="medium",
    )
    with brand:
        logo_uri = _brand_logo_data_uri()
        if logo_uri:
            st.markdown(
                f'<div class="nav-brand-left nav-brand-logo">'
                f'<img src="{logo_uri}" alt="Kestrel" />'
                f'<span>{escape(t("brand_tagline"))}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="nav-brand-left">Kestrel'
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
        if auth_disabled():
            st.caption(t("auth_dev_mode"))
        elif email:
            st.caption(t("logged_in_as", email=email))
        else:
            st.caption(t("guest_browse"))
    with cur_btn:
        if st.button(
            code,
            key="nav_currency_pill",
            use_container_width=True,
            help="USD / EUR",
        ):
            _set_currency(CURRENCY_EUR if cur == CURRENCY_USD else CURRENCY_USD)
    with auth_btn:
        if auth_disabled():
            st.caption("DEV")
        elif logged_in:
            if st.button(t("logout"), key="nav_logout", use_container_width=True):
                auth_mod.sign_out()
                auth_mod.persist_cookies_now()
                st.rerun()
        else:
            if st.button(t("login_signin"), key="nav_login", use_container_width=True):
                st.session_state["nav_page"] = "login"
                set_nav_query_params(page="login")
                st.rerun()

    return str(st.session_state["nav_page"])
