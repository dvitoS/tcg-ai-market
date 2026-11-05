# Kestrel deploy + custom domain (Creem)

Goal: public Soft Ink web on **your** domain, so Creem / payments accept the store URL.

```
Users  →  https://app.YOURDOMAIN.com     (Vercel — Soft Ink Next.js in /web)
       →  https://api.YOURDOMAIN.com     (Railway/Render — FastAPI in /api)
       →  Supabase (Auth + Postgres)
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
  (include `https://app.YOURDOMAIN.com/auth/reset` for Soft Ink password recovery)

API forgot-password uses `SOFT_INK_URL` (or the client-sent `redirect_to`) so recovery emails land on Soft Ink `/auth/reset`.

## 5. Creem checklist (approved)

After Creem accepts your custom domain:

1. **Product** — Creem → Products → create Kestrel Pro (one-time or subscription).
2. **Success URL** — product / checkout success → `https://www.kestreltcg.app/pro/success`
   (or `https://kestreltcg.app/pro/success` if that is the live host).
3. **Payment link** — Product → Share → copy link → Render API env:
   `PRO_CHECKOUT_URL=https://www.creem.io/payment/prod_...`
4. **SQL** — Supabase SQL Editor → run [`supabase_pro_entitlements.sql`](../supabase_pro_entitlements.sql).
5. **Webhook** — Creem → Developers → Webhooks → URL:
   `https://api.kestreltcg.app/api/webhooks/creem`  
   Events: `checkout.completed`, `subscription.active`, `subscription.paid`,
   `subscription.canceled`, `subscription.expired`, `subscription.past_due`.  
   Copy signing secret → Render: `CREEM_WEBHOOK_SECRET=whsec_...`
6. **Lock open beta** (when ready to charge): Render `PRO_OPEN=0`.
   With `PRO_CHECKOUT_URL` and/or `CREEM_WEBHOOK_SECRET` set, unpaid users
   are locked (no empty-allowlist fail-open). Paid emails land in
   `pro_entitlements` via webhook; optional ops override: `PRO_EMAILS=you@example.com`.
   Optional: `CREEM_PORTAL_URL` for Soft Ink “Manage subscription”.
7. Smoke: locked Dealer shows **Upgrade** → pay → land on `/pro/success` →
   sign in with checkout email → `/pro` shows You’re Pro → Dealer unlocks.
   Check `GET /api/billing/me` (`is_pro: true`, `reason: entitlement`).

## 6. Go-live smoke

1. API live + `/api/health` green with real Supabase (`source: supabase`).
2. Soft Ink live on custom domain talking to API.
3. Smoke: Landing → Browse → Detail → Portfolio login → Scanner → Dealer sample CSV → Pro.
4. Creem product + webhook + `PRO_CHECKOUT_URL` (section 5); lock with `PRO_OPEN=0` when charging.

## 7. Secrets never to commit

- `.env`, `web/.env.local`
- `SUPABASE_KEY` (service_role) only on API host — never in Vercel browser env
