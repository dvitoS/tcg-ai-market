"""Konfiguracija za Pokémon TCG API i lokalnu SQLite bazu."""

import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

# Javna dokumentacija: https://pokemontcg.io
# REST API v2: https://api.pokemontcg.io/v2
POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
POKEMON_TCG_SETS_URL = "https://api.pokemontcg.io/v2/sets"
POKEMON_TCG_DOCS_URL = "https://pokemontcg.io"

# Povijest cijena: https://api.pokewallet.io/cards/{id}/price-history
# Ključ ide u .env kao TCG_API_KEY=... i šalje se kao X-API-Key.
# Odgovor su snimke (danas, 7, 14, 30, 60 dana), ne dnevni niz.
TCG_API_KEY = os.getenv("TCG_API_KEY", "").strip()
TCG_API_BASE_URL = "https://api.pokewallet.io"
PRICE_HISTORY_DAYS = 60
API_REQUEST_DELAY_SECONDS = 0.75

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_NAME = "tcg_market.db"
DATABASE_PATH = PROJECT_ROOT / DATABASE_NAME
SEED_DATABASE_PATH = PROJECT_ROOT / "data" / "seed_tcg_market.db"
# Apsolutna putanja — ista baza lokalno i na Streamlit Cloudu.
DATABASE_URL = f"sqlite:///{DATABASE_PATH.resolve().as_posix()}"
AUTOMATION_LOG = PROJECT_ROOT / "automation.log"

DEFAULT_SET_NAME = "Scarlet & Violet"
DEFAULT_SET_ID = "sv1"
# Scarlet & Violet + Sword & Shield era (tisuće karata kroz paginaciju).
CATALOG_SERIES = (
    "Scarlet & Violet",
    "Sword & Shield",
)
# Strogi rate limit: max 100 karata / min → pageSize 100 i 1 zahtjev u ~65 s.
PAGE_SIZE = 100
RATE_LIMIT_CARDS_PER_MINUTE = 100
RATE_LIMIT_SLEEP_SECONDS = 65
RATE_LIMIT_RETRY_SLEEP_SECONDS = 90
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
NIGHTLY_TASK_NAME = "TCGMarketNightlyUpdate"
NIGHTLY_SCHEDULE_TIME = "03:00"
