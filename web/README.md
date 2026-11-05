# Kestrel Soft Ink (Next.js)

Primary public UI for Kestrel. Talks to the FastAPI app in `../api`.

Surfaces: marketing landing, browse + AI signals, card detail (multi-source chart, eBay comps, AI explain), portfolio / watchlist / alerts, scanner, dealer CSV, Kestrel Pro billing.

```bash
# from repo root — API
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# from web/
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` to the API origin (no trailing slash).
