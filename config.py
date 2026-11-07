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
        "SUPABASE_ANON_KEY": ("supabase", "anon_key"),
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


def get_supabase_auth_credentials() -> tuple[str, str]:
    """Credentials for Auth — anon key only (never service_role).

    service_role bypasses RLS; using it for login would break multi-user isolation.
    """
    url = normalize_supabase_url(_secret("SUPABASE_URL"))
    anon = _clean_secret_value(_secret("SUPABASE_ANON_KEY"))
    return url, anon


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
# Paid Soft Ink JustTCG: 1000/day, 10k/month, 50/min, 100 cards/req.
# Target ≤9000/month (≈300/day). Nightly ≤100 → Soft Ink keeps ≈200/day.
JUSTTCG_BATCH_SIZE = 100
JUSTTCG_REQUEST_DELAY_SECONDS = 1.25  # 50/min → ≥1.2s between calls
JUSTTCG_NIGHTLY_MAX_REQUESTS = 100
# Soft Ink "All" + nightly replace_card_history use this window.
# 90d keeps charts useful without the free-tier payload of 180d/1y.
JUSTTCG_HISTORY_DURATION = "90d"
PRICE_HISTORY_DAYS = 60
API_REQUEST_DELAY_SECONDS = 0.75

# Napomena: za runtime koristi get_supabase_credentials() — ove konstante
# mogu biti prazne ako se config učita prije Streamlit Secrets konteksta.
SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_KEY")
SUPABASE_DB_URL = _secret("SUPABASE_DB_URL")

SEED_DATABASE_PATH = PROJECT_ROOT / "data" / "seed_tcg_market.db"
AUTOMATION_LOG = PROJECT_ROOT / "automation.log"

# Local/dev: skip Streamlit login gate (never enable on Cloud production).
DEV_USER_ID = (
    _clean_secret_value(_secret("DEV_USER_ID"))
    or "00000000-0000-4000-8000-000000000001"
)
DEV_USER_EMAIL = _clean_secret_value(_secret("DEV_USER_EMAIL")) or "dev@local"


def _is_streamlit_cloud() -> bool:
    """Heuristic: Streamlit Community Cloud mounts the repo under /mount/src."""
    if os.getenv("STREAMLIT_CLOUD", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return Path("/mount/src").exists()


def get_soft_ink_url() -> str:
    """Public Soft Ink (Next.js) URL for Streamlit migration banner.

    Prefers SOFT_INK_URL, then KESTREL_WEB_URL. Empty → no banner.
    """
    return _clean_secret_value(_secret("SOFT_INK_URL") or _secret("KESTREL_WEB_URL"))


def auth_disabled() -> bool:
    """True when AUTH_DISABLED=1/true — bypass login for local development.

    Always False on Streamlit Cloud (multi-user). Re-reads .env on each call so a
    long-lived local Streamlit process picks up the flag without a full restart.
    """
    if _is_streamlit_cloud():
        return False
    load_dotenv(ENV_PATH, override=False)
    if not os.environ.get("GITHUB_ACTIONS"):
        load_dotenv(PROJECT_ROOT / "tcg.env.txt", override=False)
    # Prefer an explicit file value for this flag (Streamlit often starts before .env edits).
    try:
        from dotenv import dotenv_values

        file_vals = dict(dotenv_values(ENV_PATH) or {})
        file_flag = _clean_secret_value(str(file_vals.get("AUTH_DISABLED") or ""))
    except Exception:
        file_flag = ""
    raw = (
        file_flag
        or _secret("AUTH_DISABLED")
        or os.getenv("AUTH_DISABLED", "")
        or ""
    ).strip().lower()
    return raw in {"1", "true", "yes", "on"}

DEFAULT_SET_NAME = "Scarlet & Violet"
DEFAULT_SET_ID = "sv1"
# Fallback curated list when CATALOG_ALL_SETS is off / all-sets fetch fails.
# Default nightly pulls EVERY pokemontcg.io set (see catalog_all_sets_enabled).
# Pin a subset via env CATALOG_SET_IDS="sv3pt5:151,swsh7:Evolving Skies,..."
_DEFAULT_CATALOG_SETS: tuple[tuple[str, str], ...] = (
    ("sv3pt5", "151"),
    ("sv4pt5", "Paldean Fates"),
    ("sv8", "Surging Sparks"),
    ("sv8pt5", "Prismatic Evolutions"),
    ("swsh7", "Evolving Skies"),
    ("swsh11", "Lost Origin"),
    ("swsh12pt5", "Crown Zenith"),
    ("base1", "Base"),
    ("sm115", "Hidden Fates"),
)
CATALOG_SETS: tuple[tuple[str, str], ...] = _DEFAULT_CATALOG_SETS
# Used by fetch_sets_for_series when not pulling the full catalog.
CATALOG_SERIES = (
    "Scarlet & Violet",
    "Sword & Shield",
    "Sun & Moon",
    "XY",
    "Black & White",
    "HeartGold & SoulSilver",
    "Platinum",
    "Diamond & Pearl",
    "EX",
    "Neo",
    "Gym",
    "Base",
    "E-Card",
    "POP",
    "NP",
    "Other",
    "Mega Evolution",
)
# USD floor for catalog clean + board. 0 (default) = no floor, keep unpriced cards.
CATALOG_MIN_PRICE = 0.0
# When True (default) nightly/main pull every pokemontcg.io set unless CATALOG_SET_IDS is set.
CATALOG_ALL_SETS = True


def catalog_sets() -> tuple[tuple[str, str], ...]:
    """Pinned / fallback catalog sets — env override for Cloud/Actions without code edits."""
    raw = (
        _secret("CATALOG_SET_IDS") or os.getenv("CATALOG_SET_IDS", "") or ""
    ).strip()
    if not raw:
        return CATALOG_SETS
    parsed: list[tuple[str, str]] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        if ":" in piece:
            sid, name = piece.split(":", 1)
            sid, name = sid.strip(), name.strip()
            if sid and name:
                parsed.append((sid, name))
        else:
            # id-only — use id as display name
            parsed.append((piece, piece))
    return tuple(parsed) if parsed else CATALOG_SETS


def catalog_all_sets_enabled() -> bool:
    """True → resolve every pokemontcg.io set (unless CATALOG_SET_IDS pins a subset)."""
    if (_secret("CATALOG_SET_IDS") or os.getenv("CATALOG_SET_IDS", "") or "").strip():
        return False
    raw = (
        _secret("CATALOG_ALL_SETS") or os.getenv("CATALOG_ALL_SETS", "") or ""
    ).strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return bool(CATALOG_ALL_SETS)


def catalog_price_floor() -> float | None:
    """Min USD for clean_cards / board. None = keep every card (including unpriced)."""
    raw = (
        _secret("CATALOG_MIN_PRICE") or os.getenv("CATALOG_MIN_PRICE", "") or ""
    ).strip()
    if raw != "":
        try:
            value = float(raw)
        except ValueError:
            value = float(CATALOG_MIN_PRICE)
    else:
        value = float(CATALOG_MIN_PRICE)
    return None if value <= 0 else value
# pokemontcg.io allows up to 250; one page covers each curated set (largest is ~237).
PAGE_SIZE = 250
POKEMON_TCG_MAX_PAGE_SIZE = 250
RATE_LIMIT_CARDS_PER_MINUTE = 100
# pokemontcg.io is deprecated (no new keys; existing keys work until 2027-03-01).
# Unkeyed published budget ~30 req/min → ~2.5s pace. Existing keys can go faster.
RATE_LIMIT_SLEEP_SECONDS = 2.5
RATE_LIMIT_SLEEP_SECONDS_WITH_KEY = 1.5
RATE_LIMIT_RETRY_SLEEP_SECONDS = 90
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 3
CATALOG_HTTP_MAX_ATTEMPTS = 10
# Gap-fill catalog: max sets fetched per nightly when many are still missing.
NIGHTLY_CATALOG_SET_BUDGET = 50
# Batch-first JustTCG (100 cards/req, ≤100 req/night) — ~8k cards/night fits the budget.
# Full ~20k catalog refreshes in ~3 nights; missing-history cards stay prioritized.
NIGHTLY_CARD_LIMIT_DEFAULT = 8000
NIGHTLY_TASK_NAME = "TCGMarketNightlyUpdate"
NIGHTLY_SCHEDULE_TIME = "03:00"
# Soft SLO vs GitHub hard timeout (180m). Fail the job if wall clock exceeds this.
NIGHTLY_SLO_MAX_SECONDS = 150 * 60
# Soft Ink board cache TTL (seconds) — cold Radar reload without process restart.
BOARD_CACHE_TTL_SECONDS = 600


def pokemon_tcg_api_key() -> str:
    """Optional legacy pokemontcg.io key (X-Api-Key). New registrations are closed."""
    return (
        _secret("POKEMONTCG_API_KEY")
        or os.getenv("POKEMONTCG_API_KEY", "")
        or _secret("POKEMON_TCG_API_KEY")
        or os.getenv("POKEMON_TCG_API_KEY", "")
        or ""
    ).strip()


def rate_limit_sleep_seconds() -> float:
    """Seconds to wait between successful pokemontcg.io pages/sets."""
    raw = (
        _secret("POKEMONTCG_RATE_SLEEP")
        or os.getenv("POKEMONTCG_RATE_SLEEP", "")
        or ""
    ).strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    if pokemon_tcg_api_key():
        return float(RATE_LIMIT_SLEEP_SECONDS_WITH_KEY)
    return float(RATE_LIMIT_SLEEP_SECONDS)


def nightly_catalog_set_budget() -> int:
    raw = (
        _secret("NIGHTLY_CATALOG_SET_BUDGET")
        or os.getenv("NIGHTLY_CATALOG_SET_BUDGET", "")
        or ""
    ).strip()
    if raw.isdigit():
        return max(1, min(int(raw), 500))
    return int(NIGHTLY_CATALOG_SET_BUDGET)


def nightly_slo_max_seconds() -> int:
    raw = (
        _secret("NIGHTLY_SLO_MAX_SECONDS")
        or os.getenv("NIGHTLY_SLO_MAX_SECONDS", "")
        or ""
    ).strip()
    if raw.isdigit():
        return max(600, min(int(raw), 180 * 60))
    return int(NIGHTLY_SLO_MAX_SECONDS)


def justtcg_max_requests() -> int | None:
    """Soft outbound JustTCG budget for this process, or None if uncapped.

    Empty / 0 / off → unlimited (interactive Soft Ink).
    Nightly sets ~100 (≈3k/month) so ≤9k/month leaves Soft Ink daytime room.
    """
    raw = (
        _secret("JUSTTCG_MAX_REQUESTS")
        or os.getenv("JUSTTCG_MAX_REQUESTS", "")
        or ""
    ).strip().lower()
    if raw in {"", "0", "off", "none", "unlimited"}:
        return None
    if raw.isdigit():
        return max(1, min(int(raw), 1000))
    return int(JUSTTCG_NIGHTLY_MAX_REQUESTS)


def justtcg_nightly_request_budget() -> int | None:
    """Nightly hard cap — never unlimited unless explicitly allowed.

    Nov 5 burn: ``card_limit=all`` + per-card set sync with no budget burned
    thousands of JustTCG calls before cancel. Empty env must not mean unlimited
    on the Actions runner.
    """
    allow = (
        _secret("NIGHTLY_ALLOW_UNLIMITED_JUSTTCG")
        or os.getenv("NIGHTLY_ALLOW_UNLIMITED_JUSTTCG", "")
        or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    raw = (
        _secret("JUSTTCG_MAX_REQUESTS")
        or os.getenv("JUSTTCG_MAX_REQUESTS", "")
        or ""
    ).strip().lower()
    if raw in {"0", "off", "none", "unlimited"}:
        if allow:
            return None
        return int(JUSTTCG_NIGHTLY_MAX_REQUESTS)
    if raw.isdigit():
        return max(1, min(int(raw), 1000))
    # Empty / missing → default nightly cap (not Soft Ink's unlimited).
    return int(JUSTTCG_NIGHTLY_MAX_REQUESTS)


def board_cache_ttl_seconds() -> float:
    raw = (
        _secret("BOARD_CACHE_TTL_SECONDS")
        or os.getenv("BOARD_CACHE_TTL_SECONDS", "")
        or ""
    ).strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return float(BOARD_CACHE_TTL_SECONDS)
