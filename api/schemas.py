"""Pydantic response / request models for the public API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "kestrel-api"
    source: Literal["supabase", "demo", "empty"] = "empty"
    # Ops diagnostics only — never include secret values.
    creem_webhook_secret: bool = False
    pro_checkout_url: bool = False
    pro_open: bool = True
    # Deploy fingerprint (Render sets RENDER_GIT_COMMIT).
    git_sha: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    dev: bool = False


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    user: AuthUser


class MeResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None


class CatalogCard(BaseModel):
    id: str
    name: str
    set_name: str | None = None
    rarity: str | None = None
    supertype: str | None = None
    price: float | None = None
    market_price: float | None = None
    predicted_price: float | None = None
    expected_change_pct: float | None = None
    price_change_7d_pct: float | None = None
    signal: str | None = None
    confidence_ok: bool = True
    conformal_ok: bool = True
    confidence_level: str | None = None
    history_points: int = 0
    image_url: str | None = None


class CatalogMeta(BaseModel):
    total: int
    sets: list[str] = Field(default_factory=list)
    signals: dict[str, int] = Field(default_factory=dict)
    price_min: float = 0.0
    price_max: float = 100.0
    source: Literal["supabase", "demo", "empty"] = "empty"


class CatalogResponse(BaseModel):
    items: list[CatalogCard]
    total: int
    limit: int
    offset: int
    meta: CatalogMeta


class HistoryPoint(BaseModel):
    date: str
    price: float


class HistoryStats(BaseModel):
    points: int = 0
    min_price: float | None = None
    max_price: float | None = None
    last_price: float | None = None
    previous_price: float | None = None
    day_change_pct: float | None = None
    first_date: str | None = None
    last_date: str | None = None


class ExplainRow(BaseModel):
    label: str
    value: str


class CardExplain(BaseModel):
    confidence_level: str = "low"
    confidence_ok: bool = False
    confidence_reason: str = ""
    hold_band_pct: float = 0.0
    horizon_days: int = 7
    rows: list[ExplainRow] = Field(default_factory=list)


class CardDetailResponse(BaseModel):
    card: CatalogCard
    pred_lo_pct: float | None = None
    pred_hi_pct: float | None = None
    history: HistoryStats = Field(default_factory=HistoryStats)
    explain: CardExplain = Field(default_factory=CardExplain)
    source: Literal["supabase", "demo", "empty"] = "empty"


class CardHistoryResponse(BaseModel):
    card_id: str
    points: list[HistoryPoint]
    stats: HistoryStats = Field(default_factory=HistoryStats)


class SignalBoardResponse(BaseModel):
    buys: list[CatalogCard]
    sells: list[CatalogCard]
    holds: list[CatalogCard]
    source: Literal["supabase", "demo", "empty"] = "empty"


class PortfolioLot(BaseModel):
    id: int | str
    user_id: str | None = None
    card_id: str
    quantity: int
    purchase_price: float
    purchase_date: str | None = None
    condition: str | None = "NM"
    grade: str | None = None
    status: str = "open"
    sale_price: float | None = None
    sale_date: str | None = None
    name: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    image_url: str | None = None
    market_price: float | None = None
    current_price: float | None = None
    invested: float | None = None
    market_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    signal: str | None = None
    expected_change_pct: float | None = None
    predicted_price: float | None = None
    outlook_value: float | None = None


class PortfolioSummary(BaseModel):
    lots: int = 0
    value: float = 0.0
    invested: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    outlook_value: float = 0.0
    outlook_pct: float = 0.0


class PortfolioResponse(BaseModel):
    items: list[PortfolioLot]
    summary: PortfolioSummary
    demo: bool = False


class AddLotRequest(BaseModel):
    card_id: str
    quantity: int = 1
    purchase_price: float
    condition: str = "NM"
    grade: str | None = None
    purchase_date: str | None = None


class UpdateLotRequest(BaseModel):
    quantity: int | None = None
    purchase_price: float | None = None
    condition: str | None = None
    grade: str | None = None
    purchase_date: str | None = None


class SellLotRequest(BaseModel):
    sale_price: float
    sale_date: str | None = None


class WatchlistItem(BaseModel):
    id: int | str | None = None
    user_id: str | None = None
    card_id: str
    created_at: str | None = None
    name: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    image_url: str | None = None
    market_price: float | None = None
    signal: str | None = None
    expected_change_pct: float | None = None
    predicted_price: float | None = None


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    demo: bool = False


class AddWatchRequest(BaseModel):
    card_id: str


class WatchAlertItem(BaseModel):
    card_id: str
    name: str
    expected_pct: float = 0.0
    price_change_pct: float | None = None
    signal: str | None = None
    price: float = 0.0
    reason: Literal["ai", "price", "both"] | str = "ai"
    conformal_ok: bool = True
    sure: bool = False
    body: str


class WatchAlertsResponse(BaseModel):
    items: list[WatchAlertItem]
    threshold_pct: float = 5.0
    sure_only: bool = False
    sure_only_allowed: bool = True
    watch_count: int = 0
    demo: bool = False
    source: Literal["supabase", "demo", "empty"] = "empty"


class ScannerCard(CatalogCard):
    current_price: float | None = None
    ai_target_price: float | None = None
    expected_roi_pct: float | None = None


class ScannerResponse(BaseModel):
    forecast_days: int = 7
    growth_floor: float = 10.0
    min_growth: float = 10.0
    scoped: int = 0
    opp_total: int = 0
    warn_total: int = 0
    sets: list[str] = Field(default_factory=list)
    rarities: list[str] = Field(default_factory=list)
    opportunities: list[ScannerCard] = Field(default_factory=list)
    warnings: list[ScannerCard] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"


class DealerRequest(BaseModel):
    csv_text: str
    fee_pct: float | None = None
    ship_usd: float | None = None


class DealerRow(BaseModel):
    card_id: str | None = None
    name: str | None = None
    set_name: str | None = None
    quantity: int = 1
    unit_cost: float | None = None
    matched: bool = False
    spot: float | None = None
    expected_change_pct: float | None = None
    signal: str | None = None
    conformal_ok: bool = False
    pred_lo_pct: float | None = None
    pred_hi_pct: float | None = None
    net_now: float | None = None
    net_forecast: float | None = None
    net_edge_pct: float | None = None
    action: str = "HOLD"
    inventory_value: float | None = None


class DealerResponse(BaseModel):
    items: list[DealerRow]
    rows: int = 0
    matched: int = 0
    actionable: int = 0
    unmatched: int = 0
    inventory_value: float = 0.0
    fee_pct: float = 13.0
    ship_usd: float = 4.0
    source: Literal["supabase", "demo", "empty"] = "empty"
    demo: bool = False


class EbayListing(BaseModel):
    item_id: str | None = None
    title: str | None = None
    price: float | None = None
    currency: str | None = "USD"
    condition: str | None = None
    url: str | None = None
    image: str | None = None
    seller: str | None = None
    sold_date: str | None = None
    comp_source: str | None = None
    is_sold: bool | None = None


class EbaySoldStats(BaseModel):
    min: float | None = None
    median: float | None = None
    max: float | None = None
    n: int = 0
    is_sold: bool = False


class EbayCompsResponse(BaseModel):
    card_id: str
    configured: bool = False
    epn: bool = False
    listings: list[EbayListing] = Field(default_factory=list)
    listings_error: str | None = None
    sold: list[EbayListing] = Field(default_factory=list)
    sold_hint: str | None = None
    sold_stats: EbaySoldStats = Field(default_factory=EbaySoldStats)
    sold_fallback_active: bool = False
    active_fallback: list[EbayListing] = Field(default_factory=list)
