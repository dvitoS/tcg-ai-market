# Kestrel

Pokémon TCG market signals — price history, XGBoost forecasts, portfolio/watchlist (Supabase Auth + RLS), dealer desk, and live JustTCG / eBay comps. Catalog, scanner, and dealer browse are **public**; sign-in is required for portfolio / watchlist / alerts.

*(Repo folder may still be `tcg-ai-market`; product name is **Kestrel**. UI is Soft Ink — Next.js + FastAPI.)*

## Local (Soft Ink)

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
pip install -r requirements.txt -r requirements-api.txt -r requirements-dev.txt
cp .env.example .env   # fill keys

# API (repo root)
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# Web (second terminal)
cd web
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open `http://localhost:3000`. API docs: `http://127.0.0.1:8000/docs`. Tests: `pytest -q`.

| Path | Role |
|------|------|
| `web/` | Soft Ink (Next.js) — landing, browse, detail, portfolio, scanner, dealer, Pro |
| `api/` | FastAPI over existing `services/` + `market_quotes` (demo seed without Supabase) |

Without Supabase Auth credentials the API runs in **demo mode**. With `SUPABASE_URL` + `SUPABASE_ANON_KEY`, Soft Ink login uses real email/password.

### Deploy + custom domain (Creem)

See **[docs/DEPLOY.md](docs/DEPLOY.md)** — Vercel (`web/`) + Railway/Render API (`Dockerfile.api`, `railway.api.toml`) + `app.` / `api.` DNS.

## Supabase setup

Run SQL **once, in order** (SQL Editor), then **Project Settings → API → Reload schema**:

1. `supabase_schema.sql` — cards, history, portfolio, watchlist  
2. `supabase_rls_harden.sql` — RLS for user tables  
3. `supabase_auth_sessions.sql` — durable auth sessions  
4. `supabase_model_artifacts.sql` — persisted XGBoost  
5. `supabase_market_quotes.sql` — fast catalog boot (+ encodings + 7d price move)  
6. `supabase_ebay_liquidity.sql` — daily eBay active-depth snapshots for model features  
7. `supabase_pro_entitlements.sql` — Soft Pro grants from Creem webhooks  

Never set `AUTH_DISABLED=1` in production. After a model feature change, trigger a **nightly retrain** (or wait for schedule) so `market_quotes` match `FEATURE_COLUMNS`.

### Required secrets (API host)

| Secret | Role |
|--------|------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` (no `/rest/v1`) |
| `SUPABASE_KEY` | **service_role** — catalog, nightly, model/quotes write |
| `SUPABASE_ANON_KEY` | **anon public** — login + portfolio/watchlist JWT/RLS |

Optional: `JUSTTCG_API_KEY`, `TCG_API_KEY` (PokéWallet), eBay Browse keys, `EPN_CAMPID` (Partner Network click-out), `SUPABASE_DB_URL` (DDL), `CATALOG_SET_IDS` (pin sets), `CATALOG_ALL_SETS=0` (curated fallback), `CATALOG_MIN_PRICE` (USD floor; default `0` = all cards), `SOFT_INK_URL` (password-reset email links).

### eBay Partner Network (EPN)

Set `EPN_CAMPID` (campaign ID from [partnernetwork.ebay.com](https://partnernetwork.ebay.com/)). Detail page eBay ↗ links get `campid` / `mkcid` / `mkevt` / `customid` (e.g. `detail-active-{card_id}`). No-op without the secret. Disclosure caption shows when configured.

### Watchlist alerts (in-app + optional email)

Portfolio has **Alert threshold (%)** and a **Sure-only (conformal)** toggle (default on). Sure-only keeps conformal **BUY/SELL** with `|AI ROI| ≥ threshold` — drops uncertain intervals and pure 7d price moves.

- Global dismissible banners + Portfolio **Alert digest**
- Nightly **email digests** when SMTP is set (GitHub Actions; default sure-only)
- Nightly **Discord webhook** digest when `DISCORD_WEBHOOK_URL` is set

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

### Soft Pro gate (Creem)

Dealer desk is a Pro surface. Lock open beta with `PRO_OPEN=0`.

| Secret | Purpose |
|--------|---------|
| `PRO_OPEN` | Default `1` — everyone is Pro (open beta) |
| `PRO_EMAILS` / `PRO_USER_IDS` | Manual allowlist when `PRO_OPEN=0` |
| `PRO_CHECKOUT_URL` | Creem product payment link — Upgrade CTA on locked Dealer |
| `CREEM_WEBHOOK_SECRET` | HMAC secret for `POST /api/webhooks/creem` |

Paid checkouts write `pro_entitlements`. Success page: `/pro/success`. Full go-live steps: [docs/DEPLOY.md](docs/DEPLOY.md) §5.

### Key split (important)

- **service_role** → automation / catalog only  
- **anon + user JWT** → portfolio & watchlist (RLS `auth.uid()`)  

## What must NOT go in the repo

| Keep out | Why |
|----------|-----|
| `.env`, `tcg.env.txt`, `web/.env.local` | Live keys |
| `.data/` | Durable auth session blobs |
| `automation.log`, `*.log` | Local / Actions noise |
| Backfill progress / resume files under `data/` (except shipped seed DB) | Machine-local |
| Real Supabase service_role in Issues / commits | Rotate immediately if leaked |
| `ebay-worker/` secrets / `wrangler` local state | Separate worker |

Use `.env.example` only. Seed DB `data/seed_tcg_market.db` is intentional for empty boots.

## Nightly (GitHub Actions)

Workflow: [`.github/workflows/nightly_update.yml`](.github/workflows/nightly_update.yml) (03:00 UTC).

Actions secrets: `SUPABASE_URL`, `SUPABASE_KEY`, preferably `JUSTTCG_API_KEY`. Optional SMTP + `CATALOG_SET_IDS`.

Nightly refreshes history (sets with **missing history first**; limited runs prefer gap-fill), optionally backfills `tcgplayer_id` (default 60/night), retrains the model, emails watchlist digests when SMTP is set, and **fails** if `market_quotes` persist is empty. Also purges expired `auth_sessions`.

### Catalog scale

Default: **all** pokemontcg.io sets (~176) and **no** USD floor (`CATALOG_MIN_PRICE=0` keeps unpriced cards too). Nightly timeout is 6h to allow the full pull.

Pin a subset or restore the old floor without code change:

```text
CATALOG_SET_IDS=sv3pt5:151,sv8:Surging Sparks,swsh7:Evolving Skies
CATALOG_ALL_SETS=0
CATALOG_MIN_PRICE=5
```

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) — Python **3.12**, `libgomp1`, smoke-imports critical modules, then `pytest -q` (includes `load_exchange` fast-boot mocks). No live Supabase e2e.

## Architecture (short)

- `web/` — Soft Ink (Next.js)  
- `api/` — FastAPI for Soft Ink  
- `services/exchange.py` — fast boot (`market_quotes` + model) or full rebuild  
- **AI model** — board/scanner: **7d** forward return + set-relative + price-path liquidity + **eBay active depth / ask premium** (from `ebay_liquidity_snapshots`) + **conformal** gating; portfolio: separate **30d** artifact (`latest_30d`) with lot ADD/TRIM/HOLD coach (catalog stays 7d). Nightly also runs **expanding-window walk-forward** (`wf_folds` / `wf_direction_accuracy_pct` / `wf_rmse_vs_naive` on the artifact). Optional: `EBAY_LIQUIDITY_SAMPLE_N` (default `40`) caps nightly Browse harvest.  
- `database_*.py` — clients / catalog / user (facade: `database.py`)  
- `pokemon_tcg_client.py` / `pokewallet_client.py` — facade: `api_client.py`  
- `justtcg_client.py` + `justtcg_psa10.py` — NM vs PSA10  
- Auth: Soft Ink Bearer JWT → Supabase RLS  
