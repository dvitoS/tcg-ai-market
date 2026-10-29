"""eBay Marketplace Account Deletion webhook (HTTPS).

Zašto: eBay traži ovaj endpoint prije production API poziva
(Browse = aktivni oglasi, Insights = sold — kad odobre).

Deploy (Railway / Render / Fly):
  1. Postavi env (vidi .env.example)
  2. uvicorn ebay_webhook:app --host 0.0.0.0 --port $PORT
  3. Javni URL mora biti TOČNO isti kao u eBay Notifications formi
  4. developer.ebay.com → Application Keys → Notifications
     → Marketplace Account Deletion → Save

Challenge hash (eBay):
  SHA256(challengeCode + verificationToken + endpointUrl)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

load_dotenv(Path(__file__).resolve().parent / ".env")

LOG = logging.getLogger("tcg.ebay_webhook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

APP_ROOT = Path(__file__).resolve().parent
DELETION_LOG = APP_ROOT / "data" / "ebay_account_deletions.jsonl"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def endpoint_url() -> str:
    """Mora biti identičan URL-u u eBay Notifications (bez trailing slash razlike)."""
    return _env("EBAY_DELETION_ENDPOINT").rstrip("/")


def verification_token() -> str:
    return _env("EBAY_VERIFICATION_TOKEN")


def challenge_response(challenge_code: str, endpoint: str | None = None) -> str:
    resolved = (endpoint or endpoint_url()).rstrip("/")
    token = verification_token()
    if not resolved or not token:
        raise RuntimeError(
            "Postavi EBAY_DELETION_ENDPOINT i EBAY_VERIFICATION_TOKEN u env "
            "(ili pošalji challenge na javni URL da se endpoint izvede iz requesta)."
        )
    if resolved.upper() == "PLACEHOLDER":
        raise RuntimeError("EBAY_DELETION_ENDPOINT je još PLACEHOLDER.")
    raw = f"{challenge_code}{token}{resolved}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def append_deletion_event(payload: dict) -> None:
    """Audit log — trenutno ne držimo eBay user PII u produkcijskoj bazi."""
    DELETION_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with DELETION_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


app = FastAPI(
    title="TCG AI Market — eBay webhooks",
    docs_url="/docs",
    redoc_url=None,
)


@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    """Log svaki hit — da vidimo eBay challenge/test i točan path."""
    ua = request.headers.get("user-agent", "")
    qs = str(request.url.query)
    LOG.info("REQ %s %s qs=%s ua=%s", request.method, request.url.path, qs, ua[:120])
    response = await call_next(request)
    LOG.info("RES %s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "endpoint_configured": "yes" if endpoint_url() else "no",
        "token_configured": "yes" if verification_token() else "no",
    }


@app.get("/ebay/account-deletion")
def ebay_challenge(
    request: Request,
    challenge_code: str | None = Query(default=None, min_length=1),
):
    """eBay validation challenge (GET ?challenge_code=...).

    GET bez challenge_code → 200 (eBay ponekad prvo pinga URL).
    """
    if not challenge_code:
        return JSONResponse(
            {"status": "ok", "service": "ebay-account-deletion"},
            status_code=200,
        )

    configured = endpoint_url()
    # Ako env nije set / PLACEHOLDER — koristi javni URL koji je eBay upravo zvao.
    forwarded = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    derived = f"{forwarded}://{host}/ebay/account-deletion".rstrip("/")
    endpoint = (
        configured
        if configured and configured.upper() != "PLACEHOLDER"
        else derived
    )
    try:
        digest = challenge_response(challenge_code, endpoint=endpoint)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    LOG.info("eBay challenge OK endpoint=%s", endpoint)
    return {"challengeResponse": digest}


@app.post("/ebay/account-deletion")
async def ebay_account_deletion(request: Request):
    """Marketplace Account Deletion / Closure notification."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        append_deletion_event(payload if isinstance(payload, dict) else {"raw": payload})
    except Exception as exc:
        LOG.warning("deletion log failed: %s", exc)
    # Kad jednog dana budeš držao eBay user data — ovdje obriši po username/userId.
    LOG.info("eBay account deletion notification acknowledged")
    return Response(status_code=200)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "tcg-ai-market-ebay-webhook",
        "deletion_path": "/ebay/account-deletion",
        "hint": "Register https://YOUR_HOST/ebay/account-deletion in eBay Notifications",
    }
