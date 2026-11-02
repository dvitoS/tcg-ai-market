# TCG AI Market

Streamlit app for Pokémon TCG market history, XGBoost forecasts, portfolio/watchlist (Supabase Auth + RLS), and live JustTCG / eBay comps.

## Local

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill keys
streamlit run app.py
```

- `AUTH_DISABLED=1` skips login for single-user local work (ignored on Streamlit Cloud).
- Tests: `pytest -q`

## Streamlit Cloud

1. **Python 3.12** (App → Advanced settings). Do not use 3.13/3.14 defaults.
2. **Secrets** — paste from [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example), Save, **Reboot**.
3. Repo must include `requirements.txt` and `packages.txt` (`libgomp1` for XGBoost).
4. Never set `AUTH_DISABLED` on Cloud.

### Required secrets

| Secret | Role |
|--------|------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` (no `/rest/v1`) |
| `SUPABASE_KEY` | **service_role** — catalog, nightly, `auth_sessions`, model/quotes write |
| `SUPABASE_ANON_KEY` | **anon public** — login + portfolio/watchlist JWT/RLS |

Optional: `JUSTTCG_API_KEY`, `TCG_API_KEY` (PokéWallet), eBay Browse keys, `SUPABASE_DB_URL` (DDL).

### Watchlist email digests (optional)

In-app banners already fire when `|expected_change_pct| ≥` your portfolio threshold.

Nightly can also email digests when SMTP is set (GitHub Actions **and/or** Cloud secrets):

| Secret | Purpose |
|--------|---------|
| `SMTP_HOST` / `SMTP_PORT` | Mail server (default port `587` + STARTTLS) |
| `SMTP_USER` / `SMTP_PASSWORD` | Auth |
| `SMTP_FROM` | From address |
| `ALERT_EMAIL_TO` | Fallback recipient if user email lookup fails |
| `ALERT_THRESHOLD_PCT` | Default `5` |

Without SMTP, nightly skips email quietly.

### Supabase SQL (run once, in order)

1. `supabase_schema.sql` — cards, history, portfolio, watchlist  
2. `supabase_rls_harden.sql` — RLS for user tables  
3. `supabase_auth_sessions.sql` — durable `?sid=` login on Cloud  
4. `supabase_model_artifacts.sql` — persisted XGBoost  
5. `supabase_market_quotes.sql` — fast catalog boot (+ encoding columns)

Then **Project Settings → API → Reload schema** if PostgREST is stale.

### Key split (important)

- **service_role** → automation / catalog only  
- **anon + user JWT** → portfolio & watchlist (RLS `auth.uid()`)  
- Cloud never falls back to writing auth sessions on local disk

## Nightly (GitHub Actions)

Workflow: [`.github/workflows/nightly_update.yml`](.github/workflows/nightly_update.yml) (03:00 UTC).

Actions secrets: `SUPABASE_URL`, `SUPABASE_KEY`, preferably `JUSTTCG_API_KEY`.

Nightly refreshes history, optionally backfills `tcgplayer_id`, retrains the model, and **fails** if `market_quotes` persist is empty. It also purges expired `auth_sessions`.

## Architecture (short)

- `app.py` — Streamlit entry  
- `services/exchange.py` — fast boot (`market_quotes` + model) or full rebuild  
- `database_*.py` — clients / catalog / user (facade: `database.py`)  
- `ui/` — explore, detail, portfolio, scanner  
- Auth: opaque `?sid=` → Supabase `auth_sessions`

## Out of scope in git

- `ebay-worker/` and local backfill progress files are not required for Cloud deploy.
