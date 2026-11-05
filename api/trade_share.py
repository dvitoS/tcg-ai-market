"""Signed Trade Analyzer share tokens (self-contained URL payloads)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from config import _secret

MAX_LINES_PER_SIDE = 12
_DEMO_SECRET = "kestrel-trade-share-demo"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def share_secret() -> bytes:
    raw = str(_secret("TRADE_SHARE_SECRET") or os.getenv("TRADE_SHARE_SECRET", "") or "").strip()
    if not raw:
        raw = _DEMO_SECRET
    return raw.encode("utf-8")


def _normalize_lines(raw: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        card_id = str(item.get("card_id") or "").strip()
        if not card_id:
            continue
        try:
            qty = max(1, min(99, int(item.get("quantity") or 1)))
        except (TypeError, ValueError):
            qty = 1
        out.append({"card_id": card_id, "quantity": qty})
        if len(out) >= MAX_LINES_PER_SIDE:
            break
    return out


def encode_trade_share(
    *,
    you: list[dict[str, Any]],
    them: list[dict[str, Any]],
    fair_band_pct: float = 3.0,
) -> str:
    you_n = _normalize_lines(you)
    them_n = _normalize_lines(them)
    if not you_n and not them_n:
        raise ValueError("Add at least one card to either side.")
    payload = {
        "v": 1,
        "y": [[row["card_id"], row["quantity"]] for row in you_n],
        "t": [[row["card_id"], row["quantity"]] for row in them_n],
        "b": float(fair_band_pct),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    sig = _b64url(hmac.new(share_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_trade_share(token: str) -> dict[str, Any]:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        raise ValueError("Invalid share token.")
    body, sig = raw.rsplit(".", 1)
    if not body or not sig:
        raise ValueError("Invalid share token.")
    expected = _b64url(hmac.new(share_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid share signature.")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid share payload.") from exc
    if not isinstance(payload, dict) or int(payload.get("v") or 0) != 1:
        raise ValueError("Unsupported share version.")

    def _pairs(key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in payload.get(key) or []:
            if not isinstance(item, (list, tuple)) or len(item) < 1:
                continue
            card_id = str(item[0] or "").strip()
            if not card_id:
                continue
            try:
                qty = max(1, min(99, int(item[1] if len(item) > 1 else 1)))
            except (TypeError, ValueError):
                qty = 1
            rows.append({"card_id": card_id, "quantity": qty})
            if len(rows) >= MAX_LINES_PER_SIDE:
                break
        return rows

    you = _pairs("y")
    them = _pairs("t")
    if not you and not them:
        raise ValueError("Share has no cards.")
    try:
        band = float(payload.get("b") if payload.get("b") is not None else 3.0)
    except (TypeError, ValueError):
        band = 3.0
    band = max(0.5, min(25.0, band))
    return {"you": you, "them": them, "fair_band_pct": band}
