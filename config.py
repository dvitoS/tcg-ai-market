"""Konfiguracija za Pokémon TCG API i Supabase (PostgreSQL)."""

import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

PROJECT_ROOT = Path(__file__).resolve().parent


def _secret(name: str, default: str = "") -> str:
    """Prvo .env / OS, zatim Streamlit secrets (Cloud)."""
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st

        raw = st.secrets.get(name, default)
        return str(raw or default).strip()
    except Exception:
        return default


# Javna dokumentacija: https://pokemontcg.io
# REST API v2: https://api.pokemontcg.io/v2
POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
POKEMON_TCG_SETS_URL = "https://api.pokemontcg.io/v2/sets"
POKEMON_TCG_DOCS_URL = "https://pokemontcg.io"

# Povijest cijena: https://api.pokewallet.io/cards/{id}/price-history
TCG_API_KEY = _secret("TCG_API_KEY")
TCG_API_BASE_URL = "https://api.pokewallet.io"
PRICE_HISTORY_DAYS = 60
API_REQUEST_DELAY_SECONDS = 0.75

# Supabase (PostgreSQL u oblaku)
SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_KEY")
# Opcionalno: direktan Postgres URI za CREATE TABLE (Settings → Database).
SUPABASE_DB_URL = _secret("SUPABASE_DB_URL")

# Lokalni SQLite seed — jednokratni import u prazan Supabase.
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
