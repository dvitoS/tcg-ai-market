"""Konfiguracija za Pokémon TCG API i Supabase (PostgreSQL)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

# Lokalni env fajlovi (ne commitati tajne). U CI koristi samo Actions env.
load_dotenv(ENV_PATH)
if not os.environ.get("GITHUB_ACTIONS"):
    load_dotenv(PROJECT_ROOT / "tcg.env.txt")


def _from_streamlit_secrets(name: str) -> str:
    """Čita Streamlit Secrets (Cloud ili .streamlit/secrets.toml)."""
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return ""

    try:
        if name in secrets:
            return str(secrets[name]).strip()
    except Exception:
        pass

    # Nested: [supabase] url / key / db_url
    nested_map = {
        "SUPABASE_URL": ("supabase", "url"),
        "SUPABASE_KEY": ("supabase", "key"),
        "SUPABASE_DB_URL": ("supabase", "db_url"),
        "TCG_API_KEY": ("tcg", "api_key"),
        "JUSTTCG_API_KEY": ("justtcg", "api_key"),
        "EBAY_APP_ID": ("ebay", "app_id"),
        "EBAY_CERT_ID": ("ebay", "cert_id"),
        "EBAY_DEV_ID": ("ebay", "dev_id"),
        "EBAY_OAUTH_TOKEN": ("ebay", "oauth_token"),
        "EBAY_MARKETPLACE_ID": ("ebay", "marketplace_id"),
    }
    section_key = nested_map.get(name)
    if not section_key:
        return ""
    section, key = section_key
    try:
        section_obj = secrets[section]
        if key in section_obj:
            return str(section_obj[key]).strip()
    except Exception:
        return ""
    return ""


def _secret(name: str, default: str = "") -> str:
    """Prvo OS/.env, zatim Streamlit secrets (uvijek svježe — Cloud injektira kasnije)."""
    value = os.getenv(name, "").strip()
    if value:
        return value
    value = _from_streamlit_secrets(name)
    if value:
        return value
    return default


def _clean_secret_value(value: str) -> str:
    """Makni navodnike, BOM i whitespace (često u GitHub Secrets copy-paste)."""
    cleaned = (value or "").replace("\ufeff", "").strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned.replace("\r", "").replace("\n", "").strip()


def normalize_supabase_url(url: str) -> str:
    """Project URL only — bez /rest/v1 (klijent ga dodaje sam; inače PGRST125)."""
    cleaned = _clean_secret_value(url).rstrip("/")
    for suffix in ("/rest/v1", "/auth/v1"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip("/")
            break
    lower = cleaned.lower()
    marker = "/rest/v1"
    if marker in lower:
        cleaned = cleaned[: lower.index(marker)].rstrip("/")
    return cleaned


def get_supabase_credentials() -> tuple[str, str]:
    """Uvijek svježe SUPABASE_URL / SUPABASE_KEY (ne koristi stale module konstante)."""
    url = normalize_supabase_url(_secret("SUPABASE_URL"))
    key = _clean_secret_value(_secret("SUPABASE_KEY"))
    return url, key


def get_justtcg_api_key() -> str:
    """Svježi JustTCG key: ponovno učitaj .env, zatim OS / Streamlit Secrets."""
    load_dotenv(ENV_PATH, override=False)
    if not os.environ.get("GITHUB_ACTIONS"):
        load_dotenv(PROJECT_ROOT / "tcg.env.txt", override=False)

    candidates = (
        _secret("JUSTTCG_API_KEY"),
        os.getenv("JUSTTCG_API_KEY", ""),
        _from_streamlit_secrets("JUSTTCG_API_KEY"),
    )
    # Nested / alternativna imena u Secrets
    try:
        import streamlit as st

        secrets = st.secrets
        for path in (
            ("JUSTTCG_API_KEY",),
            ("justtcg", "api_key"),
            ("justtcg", "JUSTTCG_API_KEY"),
            ("api", "justtcg_api_key"),
        ):
            try:
                cur = secrets
                for part in path:
                    cur = cur[part]
                candidates = (*candidates, str(cur))
            except Exception:
                continue
    except Exception:
        pass

    for raw in candidates:
        cleaned = _clean_secret_value(str(raw or ""))
        if cleaned:
            return cleaned
    return ""


def get_ebay_credentials() -> tuple[str, str, str, str]:
    """Svježi eBay Production keyset + opcioni OAuth token.

    Čita .env datoteku direktno (dotenv_values) + OS + Streamlit Secrets,
    da lokalni long-running Streamlit i Cloud Secrets oba rade.

    Returns:
        (app_id, cert_id, dev_id, oauth_token)
    """
    from dotenv import dotenv_values

    load_dotenv(ENV_PATH, override=False)
    if not os.environ.get("GITHUB_ACTIONS"):
        load_dotenv(PROJECT_ROOT / "tcg.env.txt", override=False)

    file_vals: dict = {}
    try:
        file_vals = dict(dotenv_values(ENV_PATH) or {})
        if not os.environ.get("GITHUB_ACTIONS"):
            file_vals.update(
                {k: v for k, v in (dotenv_values(PROJECT_ROOT / "tcg.env.txt") or {}).items() if v}
            )
    except Exception:
        file_vals = {}

    def _pick(*names: str) -> str:
        for name in names:
            for raw in (
                file_vals.get(name),
                _secret(name),
                os.getenv(name, ""),
                _from_streamlit_secrets(name),
            ):
                cleaned = _clean_secret_value(str(raw or ""))
                if cleaned:
                    return cleaned
        # Nested Streamlit [ebay] bez mapiranog aliasa
        try:
            import streamlit as st

            section = st.secrets.get("ebay", {})
            aliases = {
                "EBAY_APP_ID": ("app_id", "APP_ID", "client_id", "CLIENT_ID"),
                "EBAY_CERT_ID": ("cert_id", "CERT_ID", "client_secret", "CLIENT_SECRET"),
                "EBAY_DEV_ID": ("dev_id", "DEV_ID"),
                "EBAY_OAUTH_TOKEN": ("oauth_token", "OAUTH_TOKEN", "access_token", "token"),
            }
            for name in names:
                for key in aliases.get(name, ()):
                    try:
                        cleaned = _clean_secret_value(str(section.get(key) or ""))
                        if cleaned:
                            return cleaned
                    except Exception:
                        continue
        except Exception:
            pass
        return ""

    app_id = _pick("EBAY_APP_ID", "EBAY_CLIENT_ID")
    cert_id = _pick("EBAY_CERT_ID", "EBAY_CLIENT_SECRET")
    dev_id = _pick("EBAY_DEV_ID")
    oauth = _pick("EBAY_OAUTH_TOKEN", "EBAY_USER_TOKEN", "EBAY_ACCESS_TOKEN")
    return app_id, cert_id, dev_id, oauth


# Javna dokumentacija: https://pokemontcg.io
POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
POKEMON_TCG_SETS_URL = "https://api.pokemontcg.io/v2/sets"
POKEMON_TCG_DOCS_URL = "https://pokemontcg.io"

TCG_API_KEY = _secret("TCG_API_KEY")
TCG_API_BASE_URL = "https://api.pokewallet.io"
JUSTTCG_API_KEY = _secret("JUSTTCG_API_KEY")
JUSTTCG_API_BASE_URL = "https://api.justtcg.com/v1"
# Free: 20 / request, 100 / day, 10 / min — drži delay ≥ 6s.
JUSTTCG_BATCH_SIZE = 20
JUSTTCG_REQUEST_DELAY_SECONDS = 6.5
JUSTTCG_HISTORY_DURATION = "30d"
PRICE_HISTORY_DAYS = 60
API_REQUEST_DELAY_SECONDS = 0.75

# Napomena: za runtime koristi get_supabase_credentials() — ove konstante
# mogu biti prazne ako se config učita prije Streamlit Secrets konteksta.
SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_KEY")
SUPABASE_DB_URL = _secret("SUPABASE_DB_URL")

SEED_DATABASE_PATH = PROJECT_ROOT / "data" / "seed_tcg_market.db"
AUTOMATION_LOG = PROJECT_ROOT / "automation.log"

DEFAULT_SET_NAME = "Scarlet & Violet"
DEFAULT_SET_ID = "sv1"
# Curated market catalog (pokemontcg.io set IDs). Prefer this over full eras —
# full SV+SWSH is 40+ sets and regularly times out / 500s mid-nightly.
CATALOG_SETS: tuple[tuple[str, str], ...] = (
    ("sv3pt5", "151"),
    ("swsh7", "Evolving Skies"),
    ("swsh12pt5", "Crown Zenith"),
    ("base1", "Base"),
    ("sm115", "Hidden Fates"),
)
# Keep for optional full-era pulls / fetch_sets_for_series default.
CATALOG_SERIES = (
    "Scarlet & Violet",
    "Sword & Shield",
    "Sun & Moon",
    "Base",
)
# Only keep cards with a spot market price at or above this (USD).
CATALOG_MIN_PRICE = 5.0
# pokemontcg.io allows up to 250; one page covers each curated set (largest is ~237).
PAGE_SIZE = 250
POKEMON_TCG_MAX_PAGE_SIZE = 250
RATE_LIMIT_CARDS_PER_MINUTE = 100
RATE_LIMIT_SLEEP_SECONDS = 65
RATE_LIMIT_RETRY_SLEEP_SECONDS = 90
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 3
CATALOG_HTTP_MAX_ATTEMPTS = 10
NIGHTLY_TASK_NAME = "TCGMarketNightlyUpdate"
NIGHTLY_SCHEDULE_TIME = "03:00"
