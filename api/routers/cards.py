"""Card detail + price history + eBay comps."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from api.catalog_service import history_stats, load_board, load_card_history, row_to_card
from api.explain_service import build_card_explain
from api.price_sources_service import build_card_price_sources
from api.schemas import (
    CardDetailResponse,
    CardExplain,
    CardHistoryResponse,
    CardPriceSourcesResponse,
    CatalogCard,
    EbayCompsResponse,
    EbayListing,
    EbaySoldStats,
    ExplainRow,
    HistoryPoint,
    HistoryStats,
    PsaGradeStats,
)
from services.ebay_listings import build_ebay_detail_payload

router = APIRouter(prefix="/cards", tags=["cards"])


def _pred_band(row) -> tuple[float | None, float | None]:
    pred_lo = row.get("pred_lo_pct")
    pred_hi = row.get("pred_hi_pct")
    try:
        pred_lo_f = float(pred_lo) if pred_lo is not None else None
    except (TypeError, ValueError):
        pred_lo_f = None
    try:
        pred_hi_f = float(pred_hi) if pred_hi is not None else None
    except (TypeError, ValueError):
        pred_hi_f = None
    return pred_lo_f, pred_hi_f


def _enrich_finishes(card: CatalogCard) -> CatalogCard:
    """Attach finish labels for Soft Ink foil — never block on live pokemontcg.io.

    Live TCGPlayer enrichment used ``fetch_pokemon_card`` with up to ~90s rate-limit
    sleeps; that made card detail feel hung after Browse clicks. Prefer catalog /
    rarity hints only on the request path.
    """
    from services.card_finishes import parse_finishes_blob, resolve_finishes

    stored = None
    rarity = card.rarity
    try:
        from database import get_card

        db_card = get_card(str(card.id))
        if db_card is not None:
            stored = getattr(db_card, "finishes", None)
            rarity = rarity or getattr(db_card, "rarity", None)
    except Exception:
        pass

    finishes = resolve_finishes(stored=stored, rarity=rarity)
    if parse_finishes_blob(stored):
        source: str | None = "catalog"
    elif finishes:
        source = "rarity"
    else:
        source = None

    payload = card.model_dump()
    payload["finishes"] = finishes
    payload["finishes_source"] = source if finishes else None
    if rarity and not payload.get("rarity"):
        payload["rarity"] = rarity
    return CatalogCard(**payload)


@router.get("/{card_id}", response_model=CardDetailResponse)
def card_detail(card_id: str) -> CardDetailResponse:
    board, source = load_board()
    if board is None or board.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    hits = board[board["id"].astype(str) == str(card_id)]
    if hits.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    row = hits.iloc[0]
    card = _enrich_finishes(CatalogCard(**row_to_card(row)))
    pred_lo_f, pred_hi_f = _pred_band(row)
    points = load_card_history(card_id, limit=180)
    stats = history_stats(points)
    explain_payload = build_card_explain(
        points=points,
        last_price=stats.get("last_price") if stats.get("last_price") is not None else card.price,
        predicted_price=card.predicted_price,
        pred_lo_pct=pred_lo_f,
        pred_hi_pct=pred_hi_f,
    )
    return CardDetailResponse(
        card=card,
        pred_lo_pct=pred_lo_f,
        pred_hi_pct=pred_hi_f,
        history=HistoryStats(**stats),
        points=[HistoryPoint(**p) for p in points],
        explain=CardExplain(
            confidence_level=str(explain_payload["confidence_level"]),
            confidence_ok=bool(explain_payload["confidence_ok"]),
            confidence_reason=str(explain_payload["confidence_reason"]),
            hold_band_pct=float(explain_payload["hold_band_pct"]),
            horizon_days=int(explain_payload["horizon_days"]),
            rows=[ExplainRow(**r) for r in explain_payload["rows"]],
        ),
        source=source,
    )


@router.get("/{card_id}/history", response_model=CardHistoryResponse)
def card_history(
    card_id: str,
    limit: int = Query(default=180, ge=7, le=730),
) -> CardHistoryResponse:
    raw = load_card_history(card_id, limit=limit)
    points = [HistoryPoint(**p) for p in raw]
    return CardHistoryResponse(
        card_id=str(card_id),
        points=points,
        stats=HistoryStats(**history_stats(raw)),
    )


@router.get("/{card_id}/sources", response_model=CardPriceSourcesResponse)
def card_price_sources(
    card_id: str,
    limit: int = Query(default=180, ge=7, le=730),
    grades: str = Query(
        default="none",
        description="Graded JustTCG prints: none (default), psa10, or all (PSA10+PSA9).",
    ),
) -> CardPriceSourcesResponse:
    payload = build_card_price_sources(str(card_id), limit=limit, grades=grades)
    cache_flag = payload.get("cache")
    grades_mode = payload.get("grades")
    return CardPriceSourcesResponse(
        card_id=str(payload["card_id"]),
        name=str(payload["name"]),
        set_name=payload.get("set_name"),
        tcgplayer_id=payload.get("tcgplayer_id"),
        justtcg_configured=bool(payload.get("justtcg_configured")),
        tcgplayer=[HistoryPoint(**p) for p in payload.get("tcgplayer") or []],
        justtcg=[HistoryPoint(**p) for p in payload.get("justtcg") or []],
        justtcg_fallback=bool(payload.get("justtcg_fallback")),
        justtcg_from_db=bool(payload.get("justtcg_from_db")),
        justtcg_error=payload.get("justtcg_error"),
        psa10=[HistoryPoint(**p) for p in payload.get("psa10") or []],
        psa10_error=payload.get("psa10_error"),
        psa10_stats=PsaGradeStats(**(payload.get("psa10_stats") or {})),
        psa9=[HistoryPoint(**p) for p in payload.get("psa9") or []],
        psa9_error=payload.get("psa9_error"),
        psa9_stats=PsaGradeStats(**(payload.get("psa9_stats") or {})),
        grades=grades_mode if grades_mode in ("none", "psa10", "all") else "none",
        cache=cache_flag if cache_flag in ("hit", "miss") else None,
    )


@router.get("/{card_id}/ebay", response_model=EbayCompsResponse)
def card_ebay_comps(
    card_id: str,
    limit: int = Query(default=8, ge=1, le=20),
) -> EbayCompsResponse:
    board, _source = load_board()
    name = str(card_id)
    set_name = ""
    if board is not None and not board.empty:
        hits = board[board["id"].astype(str) == str(card_id)]
        if not hits.empty:
            row = hits.iloc[0]
            name = str(row.get("name") or card_id)
            set_name = str(row.get("set_name") or "")

    payload = build_ebay_detail_payload(
        card_id=str(card_id),
        name=name,
        set_name=set_name,
        limit=limit,
    )
    return EbayCompsResponse(
        card_id=str(card_id),
        configured=bool(payload.get("configured")),
        epn=bool(payload.get("epn")),
        listings=[EbayListing(**r) for r in (payload.get("listings") or []) if isinstance(r, dict)],
        listings_error=payload.get("listings_error"),
        sold=[EbayListing(**r) for r in (payload.get("sold") or []) if isinstance(r, dict)],
        sold_hint=payload.get("sold_hint"),
        sold_stats=EbaySoldStats(**(payload.get("sold_stats") or {})),
        sold_fallback_active=bool(payload.get("sold_fallback_active")),
        active_fallback=[
            EbayListing(**r) for r in (payload.get("active_fallback") or []) if isinstance(r, dict)
        ],
    )
