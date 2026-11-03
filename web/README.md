# Kestrel web (Next.js)

Soft Ink frontend for Kestrel. Talks to the FastAPI app in `../api`.

```bash
# from repo root — API
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# from web/
cp .env.example .env.local
npm install
npm run dev
```

Phase 1–2: shell, Browse Market, card detail stub. Portfolio / Scanner / Dealer come later.
