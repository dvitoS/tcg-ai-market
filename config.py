"""Konfiguracija za Pokémon TCG API i lokalnu SQLite bazu."""

# Javna dokumentacija: https://pokemontcg.io
# REST API v2: https://api.pokemontcg.io/v2
POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
POKEMON_TCG_DOCS_URL = "https://pokemontcg.io"

DATABASE_NAME = "tcg_market.db"
DATABASE_URL = f"sqlite:///{DATABASE_NAME}"

DEFAULT_SET_NAME = "Scarlet & Violet"
DEFAULT_SET_ID = "sv1"
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
