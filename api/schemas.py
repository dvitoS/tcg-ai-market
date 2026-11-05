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


class DataHealthResponse(BaseModel):
    """Process-wide JustTCG / Soft Ink price-source outcomes since API boot."""

    live: int = 0
    db: int = 0
    empty: int = 0
    fallback: int = 0
    error: int = 0
    cache_hit: int = 0
    attempts: int = 0
    miss_or_fallback_pct: float = 0.0
    justtcg_configured: bool = False


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str
    redirect_to: str | None = None


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str


class UpdatePasswordRequest(BaseModel):
    password: str
    refresh_token: str | None = None


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    dev: bool = False


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    user: AuthUser


class SignupResponse(BaseModel):
    needs_confirmation: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    user: AuthUser | None = None
    message: str | None = None


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


class Psa10Stats(BaseModel):
    has_history_series: bool = False
    period_key: str | None = None
    sales_count: int | float | None = None


class CardPriceSourcesResponse(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    tcgplayer_id: str | None = None
    justtcg_configured: bool = False
    tcgplayer: list[HistoryPoint] = Field(default_factory=list)
    justtcg: list[HistoryPoint] = Field(default_factory=list)
    justtcg_fallback: bool = False
    justtcg_from_db: bool = False
    justtcg_error: str | None = None
    psa10: list[HistoryPoint] = Field(default_factory=list)
    psa10_error: str | None = None
    psa10_stats: Psa10Stats = Field(default_factory=Psa10Stats)
    cache: Literal["hit", "miss"] | None = None


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
    printing: str | None = "Normal"
    grade: str | None = None
    status: str = "open"
    sale_price: float | None = None
    sale_date: str | None = None
    name: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    image_url: str | None = None
    nm_market_price: float | None = None
    price_factor: float | None = None
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
    outlook_roi_pct: float | None = None
    outlook_lo_pct: float | None = None
    outlook_hi_pct: float | None = None
    outlook_conformal_ok: bool | None = None
    outlook_horizon_days: int | None = None
    lot_action: str | None = None
    is_top_ai: bool | None = None


class PortfolioSummary(BaseModel):
    lots: int = 0
    value: float = 0.0
    invested: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    outlook_value: float = 0.0
    outlook_pct: float = 0.0
    outlook_horizon_days: int = 7


class PortfolioResponse(BaseModel):
    items: list[PortfolioLot]
    summary: PortfolioSummary
    demo: bool = False


class PortfolioPerfPoint(BaseModel):
    date: str
    invested: float
    market_value: float
    ai_fair_value: float | None = None
    ai_lo: float | None = None
    ai_hi: float | None = None


class PortfolioDrawdownCallout(BaseModel):
    peak_date: str
    trough_date: str
    drawdown_pct: float
    peak_value: float
    trough_value: float
    trim_count: int = 0
    note: str = ""


class PortfolioPerformanceResponse(BaseModel):
    points: list[PortfolioPerfPoint]
    days: int = 0
    demo: bool = False
    ai_fair_value: float | None = None
    ai_lo: float | None = None
    ai_hi: float | None = None
    drawdown_callouts: list[PortfolioDrawdownCallout] = Field(default_factory=list)


class AddLotRequest(BaseModel):
    card_id: str
    quantity: int = 1
    purchase_price: float
    condition: str = "NM"
    printing: str = "Normal"
    grade: str | None = None
    purchase_date: str | None = None


class UpdateLotRequest(BaseModel):
    quantity: int | None = None
    purchase_price: float | None = None
    condition: str | None = None
    printing: str | None = None
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


class RadarCard(CatalogCard):
    side: Literal["UNDER", "OVER"] = "UNDER"
    edge_pct: float | None = None
    spot: float | None = None
    fair_price: float | None = None
    pred_lo_pct: float | None = None
    pred_hi_pct: float | None = None
    current_price: float | None = None
    ai_target_price: float | None = None
    expected_roi_pct: float | None = None


class RadarStatus(BaseModel):
    allowed: bool
    reason: str = ""
    checkout_url: str | None = None
    forecast_days: int = 7
    edge_floor: float = 0.0


class RadarResponse(BaseModel):
    forecast_days: int = 7
    edge_floor: float = 0.0
    min_edge: float = 0.0
    scoped: int = 0
    sure_scoped: int = 0
    under_total: int = 0
    over_total: int = 0
    sets: list[str] = Field(default_factory=list)
    rarities: list[str] = Field(default_factory=list)
    underpriced: list[RadarCard] = Field(default_factory=list)
    overpriced: list[RadarCard] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"


class RadarPreviewResponse(BaseModel):
    """Public teaser — top UNDER edges only (no Pro auth)."""

    forecast_days: int = 7
    under_total: int = 0
    underpriced: list[RadarCard] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"


class TradeLineIn(BaseModel):
    card_id: str
    quantity: int = 1
    condition: str = "NM"
    printing: str = "Normal"


class TradeRequest(BaseModel):
    you: list[TradeLineIn] = Field(default_factory=list)
    them: list[TradeLineIn] = Field(default_factory=list)
    fair_band_pct: float | None = None


class TradeLineOut(BaseModel):
    card_id: str
    quantity: int = 1
    condition: str = "NM"
    printing: str = "Normal"
    price_factor: float = 1.0
    matched: bool = False
    name: str | None = None
    set_name: str | None = None
    image_url: str | None = None
    spot: float | None = None
    fair_price: float | None = None
    expected_change_pct: float | None = None
    pred_lo_pct: float | None = None
    pred_hi_pct: float | None = None
    signal: str | None = None
    conformal_ok: bool = False
    line_spot: float | None = None
    line_fair: float | None = None


class TradeSide(BaseModel):
    lines: list[TradeLineOut] = Field(default_factory=list)
    matched: int = 0
    unmatched: int = 0
    spot_total: float = 0.0
    fair_total: float = 0.0
    cards: int = 0


class TradeStatus(BaseModel):
    allowed: bool
    reason: str = ""
    checkout_url: str | None = None
    fair_band_pct: float = 3.0


class TradeResponse(BaseModel):
    you: TradeSide
    them: TradeSide
    net_spot_usd: float = 0.0
    net_fair_usd: float = 0.0
    net_spot_pct: float = 0.0
    net_fair_pct: float = 0.0
    spot_verdict: str = "FAIR"
    ai_verdict: str = "FAIR"
    verdict: str = "FAIR"
    fair_band_pct: float = 3.0
    source: Literal["supabase", "demo", "empty"] = "empty"


class TradeShareCreated(BaseModel):
    id: str
    path: str
    url: str | None = None


class TradeShareView(TradeResponse):
    """Public share payload — live re-score plus Soft Pro CTA."""

    checkout_url: str | None = None
    share_id: str = ""


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
