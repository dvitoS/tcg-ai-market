# Kestrel deploy + custom domain (Creem)

Goal: public Soft Ink web on **your** domain (not `*.streamlit.app`), so Creem / payments accept the store URL.

```
Users  →  https://app.YOURDOMAIN.com     (Vercel — Next.js in /web)
       →  https://api.YOURDOMAIN.com     (Railway/Render — FastAPI in /api)
       →  Supabase (Auth + Postgres)
Streamlit can stay up until cutover.
```

## 1. Domain

1. Buy a domain (Cloudflare Registrar / Namecheap / etc.).
2. Prefer Cloudflare DNS (easy CNAME + SSL).
3. Plan records:
   - `app` → Vercel
   - `api` → Railway / Render
   - optional apex `YOURDOMAIN.com` → marketing / redirect to `app`

## 2. API (Railway recommended)

You already have `railway.toml` for the **eBay webhook**. Deploy Soft Ink API as a **second** service:

1. Railway → New service → this GitHub repo.
2. Settings → Config file: `railway.api.toml` (uses `Dockerfile.api`).
3. Variables (minimum):

| Variable | Notes |
|----------|--------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | service_role (catalog / quotes) |
| `SUPABASE_ANON_KEY` | anon public (login + RLS) |
| `KESTREL_CORS_ORIGINS` | `https://app.YOURDOMAIN.com,https://YOURDOMAIN.com` |
| `AUTH_DISABLED` | `0` in production |
| `PRO_OPEN` | `1` for open beta, else allowlist |

4. Networking → Generate domain, then add custom `api.YOURDOMAIN.com`.
5. Health check path is `/api/health`.

Alternative: Render Blueprint via root `render.yaml`.

Local Docker shape:

```bash
docker compose up --build api
curl -s http://127.0.0.1:8000/api/health
```

## 3. Web (Vercel)

1. Vercel → Add New Project → import repo.
2. **Root Directory:** `web`
3. Framework: Next.js (auto). Region: `fra1` (see `web/vercel.json`) or closer to you.
4. Environment variables:

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | `https://api.YOURDOMAIN.com` (no trailing slash) |

5. Deploy, then Domains → add `app.YOURDOMAIN.com` (follow DNS CNAME).
6. Confirm:
   - `https://app.YOURDOMAIN.com` loads Browse
   - Network tab calls `https://api.YOURDOMAIN.com/api/catalog`

## 4. Supabase Auth URLs

In Supabase → Authentication → URL configuration:

- Site URL: `https://app.YOURDOMAIN.com`
- Redirect URLs: `https://app.YOURDOMAIN.com/**`

## 5. Creem checklist

Creem rejected `tcg-ai-market.streamlit.app` because it is not your domain.

After DNS is live:

1. Open Creem store settings.
2. Set **Website URL** to `https://app.YOURDOMAIN.com` (or apex if that is the product site).
3. Save and re-submit / wait for review.
4. Keep Streamlit URL private for ops until you cut over.

## 6. Cutover order

1. API live + `/api/health` green with real Supabase.
2. Web live on custom domain talking to API.
3. Smoke: Browse → Detail → Portfolio login → Scanner → Dealer sample CSV.
4. Point Creem to the custom domain.
5. Later: turn down Streamlit Community Cloud when Soft Ink replaces it.

## 7. Secrets never to commit

- `.env`, `web/.env.local`, Streamlit secrets
- `SUPABASE_KEY` (service_role) only on API host — never in Vercel browser env
