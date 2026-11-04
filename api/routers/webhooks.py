"""Inbound billing webhooks (Creem)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from services.creem_webhooks import creem_webhook_secret, handle_creem_event, verify_creem_signature

LOG = logging.getLogger("kestrel.api.webhooks")

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/creem")
async def creem_webhook(request: Request) -> dict:
    secret = creem_webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CREEM_WEBHOOK_SECRET is not configured.",
        )

    raw = await request.body()
    signature = (
        request.headers.get("creem-signature")
        or request.headers.get("Creem-Signature")
        or request.headers.get("x-creem-signature")
    )
    if not verify_creem_signature(raw, signature, secret):
        LOG.warning("Rejected Creem webhook: bad signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Creem signature.",
        )

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be an object.",
        )

    event_type = str(payload.get("eventType") or payload.get("event_type") or "")
    event_id = str(payload.get("id") or "")
    LOG.info("Creem webhook received id=%s type=%s", event_id, event_type)

    result = handle_creem_event(payload)
    LOG.info("Creem webhook handled: %s", result)

    # Non-ok grants must not ack 200 — Creem only retries on non-2xx.
    if not result.get("ok", False) and result.get("action") in {"grant", "revoke"}:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result,
        )
    return result
