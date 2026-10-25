"""Konfiguracija za Pokémon TCG API i Supabase (PostgreSQL)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

# Lokalni env fajlovi (ne commitati tajne).
load_dotenv(ENV_PATH)
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


def normalize_supabase_url(url: str) -> str:
    """Project URL only — bez /rest/v1 (klijent ga dodaje sam; inače PGRST125)."""
    cleaned = (url or "").strip().strip('"').strip("'").rstrip("/")
    for suffix in ("/rest/v1", "/rest/v1/", "/auth/v1", "/auth/v1/"):
        if cleaned.lower().endswith(suffix.rstrip("/")):
            cleaned = cleaned[: -len(suffix.rstrip("/"))].rstrip("/")
            break
    # Često: zalijepljen cijeli REST endpoint s trailing slashom.
    lower = cleaned.lower()
    marker = "/rest/v1"
    if marker in lower:
        cleaned = cleaned[: lower.index(marker)].rstrip("/")
    return cleaned


def get_supabase_credentials() -> tuple[str, str]:
    """Uvijek svježe SUPABASE_URL / SUPABASE_KEY (ne koristi stale module konstante)."""
    url = normalize_supabase_url(_secret("SUPABASE_URL"))
    key = _secret("SUPABASE_KEY").strip().strip('"').strip("'")
    return url, key


# Javna dokumentacija: https://pokemontcg.io
POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
POKEMON_TCG_SETS_URL = "https://api.pokemontcg.io/v2/sets"
POKEMON_TCG_DOCS_URL = "https://pokemontcg.io"

TCG_API_KEY = _secret("TCG_API_KEY")
TCG_API_BASE_URL = "https://api.pokewallet.io"
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
CATALOG_SERIES = (
    "Scarlet & Violet",
    "Sword & Shield",
)
PAGE_SIZE = 100
RATE_LIMIT_CARDS_PER_MINUTE = 100
RATE_LIMIT_SLEEP_SECONDS = 65
RATE_LIMIT_RETRY_SLEEP_SECONDS = 90
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
NIGHTLY_TASK_NAME = "TCGMarketNightlyUpdate"
NIGHTLY_SCHEDULE_TIME = "03:00"
