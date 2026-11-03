# Kestrel

Pokémon TCG market signals — price history, XGBoost forecasts, portfolio/watchlist (Supabase Auth + RLS), dealer desk, and live JustTCG / eBay comps. Catalog, scanner, and dealer browse are **public**; sign-in is required for portfolio / watchlist / alerts.

*(Repo folder may still be `tcg-ai-market`; product name is **Kestrel**.)*

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

## Web rewrite (Next.js + FastAPI) — in progress

Streamlit stays the production UI until cutover. New surface:

| Path | Role |
|------|------|
| `api/` | FastAPI over existing `services/` + `market_quotes` (falls back to `data/seed_tcg_market.db` demo) |
| `web/` | Next.js Soft Ink — Browse, detail + chart, portfolio/watchlist, scanner, dealer |

Without Supabase Auth credentials the API runs in **demo mode** (seeded lots + watchlist). With `SUPABASE_URL` + `SUPABASE_ANON_KEY`, login uses real Supabase email/password.

```bash
# API (repo root)
pip install -r requirements.txt -r requirements-api.txt
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# Web (second terminal)
cd web
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open `http://localhost:3000` (Portfolio at `/portfolio`). Docs: `http://127.0.0.1:8000/docs`.

### Deploy + custom domain (Creem)

See **[docs/DEPLOY.md](docs/DEPLOY.md)** — Vercel (`web/`) + Railway/Render API (`Dockerfile.api`, `railway.api.toml`) + `app.` / `api.` DNS so Creem accepts your store URL instead of `*.streamlit.app`.

## Deploy checklist (Streamlit Cloud)

Do this once per environment — saves hours of Cloud debug later.

1. **Python 3.12** — App → Advanced settings. Do **not** use 3.13/3.14 defaults (XGBoost / binary wheels).
2. **Secrets** — paste from [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example), Save, **Reboot**.
3. Repo root must include `requirements.txt` and `packages.txt` (`libgomp1` for XGBoost).
4. Run Supabase SQL **once, in order** (SQL Editor), then **Project Settings → API → Reload schema**:
   1. `supabase_schema.sql` — cards, history, portfolio, watchlist  
   2. `supabase_rls_harden.sql` — RLS for user tables  
   3. `supabase_auth_sessions.sql` — durable `?sid=` login on Cloud  
   4. `supabase_model_artifacts.sql` — persisted XGBoost  
   5. `supabase_market_quotes.sql` — fast catalog boot (+ encodings + 7d price move)  
   6. `supabase_ebay_liquidity.sql` — daily eBay active-depth snapshots for model features
5. Never set `AUTH_DISABLED` on Cloud.
6. After a model feature change (e.g. set-relative), trigger a **nightly retrain** (or wait for schedule) so `market_quotes` match `FEATURE_COLUMNS`.

### Required secrets

| Secret | Role |
|--------|------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` (no `/rest/v1`) |
| `SUPABASE_KEY` | **service_role** — catalog, nightly, `auth_sessions`, model/quotes write |
| `SUPABASE_ANON_KEY` | **anon public** — login + portfolio/watchlist JWT/RLS |

Optional: `JUSTTCG_API_KEY`, `TCG_API_KEY` (PokéWallet), eBay Browse keys, `EPN_CAMPID` (Partner Network click-out), `SUPABASE_DB_URL` (DDL), `CATALOG_SET_IDS` (override curated sets).

### eBay Partner Network (EPN)

Set `EPN_CAMPID` (campaign ID from [partnernetwork.ebay.com](https://partnernetwork.ebay.com/)). Detail page eBay ↗ links get `campid` / `mkcid` / `mkevt` / `customid` (e.g. `detail-active-{card_id}`). No-op without the secret. Disclosure caption shows when configured.

### Watchlist alerts (in-app + optional email)

Portfolio has **Alert threshold (%)** and a **Sure-only (conformal)** toggle (default on). Sure-only keeps conformal **BUY/SELL** with `|AI ROI| ≥ threshold` — drops uncertain intervals and pure 7d price moves.

- Top-of-app dismissible banners
- Portfolio **Alert digest** expander
- Nightly **email digests** when SMTP is set (GitHub Actions **and/or** Cloud secrets; default sure-only)
- Nightly **Discord webhook** digest when `DISCORD_WEBHOOK_URL` is set (aggregated sure-only across watchlists)

| Secret | Purpose |
|--------|---------|
| `SMTP_HOST` / `SMTP_PORT` | Mail server (default port `587` + STARTTLS) |
| `SMTP_USER` / `SMTP_PASSWORD` | Auth |
| `SMTP_FROM` | From address |
| `ALERT_EMAIL_TO` | Fallback recipient if user email lookup fails |
| `ALERT_THRESHOLD_PCT` | Default `5` (email path; UI threshold is per session) |
| `ALERT_SURE_ONLY` | Default `1` — nightly conformal BUY/SELL only (`0` = legacy) |
| `DISCORD_WEBHOOK_URL` | Channel webhook for one nightly sure-only digest |

Without SMTP/Discord, nightly skips those quietly; in-app digest still works.

### Dealer desk

Nav → **Dealer**. Upload inventory CSV (`card_id`/`id` or `name`, optional `quantity`/`cost`). The desk joins your rows to the live 7d AI board, applies sell fee + shipping, and ranks **LIST / BUY MORE / HOLD** only when the conformal gate is green. Download scored CSV from the full table.

### Soft Pro gate

Until Stripe/Lemon: Dealer desk + sure-only alerts are Pro surfaces.

| Secret | Purpose |
|--------|---------|
| `PRO_OPEN` | Default `1` — everyone is Pro (open beta) |
| `PRO_EMAILS` | Comma-separated emails when `PRO_OPEN=0` |
| `PRO_USER_IDS` | Comma-separated Supabase user UUIDs when `PRO_OPEN=0` |
| `PRO_CHECKOUT_URL` | Optional Lemon/Stripe Payment Link — “Upgrade to Pro” on locked surfaces |

`AUTH_DISABLED` local always counts as Pro. Empty allowlist with `PRO_OPEN=0` stays open (avoids locking everyone out). After someone pays, add their email to `PRO_EMAILS` (webhook automation later).

### Key split (important)

- **service_role** → automation / catalog only  
- **anon + user JWT** → portfolio & watchlist (RLS `auth.uid()`)  
- Cloud never falls back to writing auth sessions on local disk

## What must NOT go in the repo

| Keep out | Why |
|----------|-----|
| `.env`, `tcg.env.txt`, `.streamlit/secrets.toml` | Live keys |
| `.data/` | Durable auth session blobs |
| `automation.log`, `*.log` | Local / Actions noise |
| Backfill progress / resume files under `data/` (except shipped seed DB) | Machine-local |
| Real Supabase service_role in Issues / commits | Rotate immediately if leaked |
| `ebay-worker/` secrets / `wrangler` local state | Separate worker |

Use `.env.example` and `secrets.toml.example` only. Seed DB `data/seed_tcg_market.db` is intentional for empty Cloud boots.

## Nightly (GitHub Actions)

Workflow: [`.github/workflows/nightly_update.yml`](.github/workflows/nightly_update.yml) (03:00 UTC).

Actions secrets: `SUPABASE_URL`, `SUPABASE_KEY`, preferably `JUSTTCG_API_KEY`. Optional SMTP + `CATALOG_SET_IDS`.

Nightly refreshes history (sets with **missing history first**; limited runs prefer gap-fill), optionally backfills `tcgplayer_id` (default 60/night), retrains the model, emails watchlist digests when SMTP is set, and **fails** if `market_quotes` persist is empty. Also purges expired `auth_sessions`.

### Catalog scale

Default curated sets (pokemontcg.io ids): 151, Paldean Fates, Surging Sparks, Prismatic Evolutions, Evolving Skies, Lost Origin, Crown Zenith, Base, Hidden Fates — `$5+` floor.

Override without code change:

```text
CATALOG_SET_IDS=sv3pt5:151,sv8:Surging Sparks,swsh7:Evolving Skies
```

Keep the list curated — full SV+SWSH regularly times out mid-nightly.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) — Python **3.12**, `libgomp1`, smoke-imports critical modules, then `pytest -q` (includes `load_exchange` fast-boot mocks). No live Supabase / Streamlit e2e.

## Architecture (short)

- `app.py` — Streamlit entry  
- `services/exchange.py` — fast boot (`market_quotes` + model) or full rebuild  
- **AI model** — board/scanner: **7d** forward return + set-relative + price-path liquidity + **eBay active depth / ask premium** (from `ebay_liquidity_snapshots`) + **conformal** gating; portfolio: separate **30d** artifact (`latest_30d`) with lot ADD/TRIM/HOLD coach (catalog stays 7d). Nightly also runs **expanding-window walk-forward** (`wf_folds` / `wf_direction_accuracy_pct` / `wf_rmse_vs_naive` on the artifact). Optional: `EBAY_LIQUIDITY_SAMPLE_N` (default `40`) caps nightly Browse harvest.  
- `database_*.py` — clients / catalog / user (facade: `database.py`)  
- `pokemon_tcg_client.py` / `pokewallet_client.py` — facade: `api_client.py`  
- `justtcg_client.py` + `justtcg_psa10.py` — NM vs PSA10  
- `ui/` — explore, detail, portfolio, scanner, **dealer desk** (CSV inventory × fee-aware AI)  
- Auth: opaque `?sid=` → Supabase `auth_sessions`
