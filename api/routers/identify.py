"""Camera OCR → catalog identify (text in, ranked Soft Ink cards out)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.identify_service import identify_from_text
from api.schemas import CatalogCard, IdentifyMatch, IdentifyRequest, IdentifyResponse

router = APIRouter(tags=["identify"])


@router.post("/identify", response_model=IdentifyResponse)
def identify_card(body: IdentifyRequest) -> IdentifyResponse:
    text = (body.text or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="OCR text too short.")
    if len(text) > 8000:
        text = text[:8000]

    payload = identify_from_text(text, limit=body.limit or 8)
    matches = [
        IdentifyMatch(
            score=float(m["score"]),
            reasons=list(m.get("reasons") or []),
            card=CatalogCard(**m["card"]),
        )
        for m in payload.get("matches") or []
    ]
    clues = payload.get("clues") or {}
    return IdentifyResponse(
        matches=matches,
        total=int(payload.get("total") or len(matches)),
        source=payload.get("source") or "empty",
        name_hints=list(clues.get("name_hints") or []),
        number=clues.get("number"),
        collector=clues.get("collector"),
    )
