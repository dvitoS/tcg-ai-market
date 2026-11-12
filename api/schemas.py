"""Pydantic response / request models for the public API."""

from __future__ import annotations

from typing import Any, Literal

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
    """Process-wide JustTCG counters + spot/history QA (Phase C2)."""

    live: int = 0
    db: int = 0
    empty: int = 0
    fallback: int = 0
    error: int = 0
    cache_hit: int = 0
    attempts: int = 0
    miss_or_fallback_pct: float = 0.0
    justtcg_configured: bool = False
    # Spot / history QA
    cards_total: int = 0
    cards_with_history: int = 0
    history_coverage_pct: float = 0.0
    fresh_history_pct: float | None = None
    sure_rows: int = 0
    quotes_total: int = 0
    spot_quarantine_rows: int = 0
    spot_poison_clusters: int = 0
    spot_poison_cluster_sample: list[dict[str, Any]] = Field(default_factory=list)
    unmatched_sets_count: int | None = None
    unmatched_sets_sample: list[dict[str, str]] = Field(default_factory=list)
    spot_qa_captured_at: str | None = None
    board_source: str = "empty"
    nightly_slo_ok: bool | None = None
    nightly_elapsed_s: float | None = None
    quotes_written: int | None = None


class SpotSniffItem(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    rarity: str | None = None
    side: Literal["UNDER", "OVER"]
    spot: float | None = None
    fair_price: float | None = None
    edge_pct: float | None = None
    tcgplayer_id: str | None = None
    tcgplayer_url: str | None = None
    kestrel_path: str
    tcp_live: float | None = None
    tcp_delta_pct: float | None = None
    tcp_status: Literal["ok", "warn", "fail", "skip"] = "skip"
    auto_status: Literal["ok", "warn", "fail", "skip"] = "skip"
    tcp_resolved: bool = False
    skip_reason: str | None = None
    ebay_median: float | None = None
    ebay_delta_pct: float | None = None
    ebay_n: int = 0
    ebay_is_sold: bool = False
    ebay_status: Literal["ok", "warn", "fail", "skip"] = "skip"
    verdict: Literal["pass", "review", "fail"] = "review"
    healed: bool = False
    check_tcp: bool | None = None
    check_ebay: bool | None = None
    notes: str = ""


class SpotSniffPackResponse(BaseModel):
    generated_at: str
    limit: int
    count: int
    under_n: int = 0
    over_n: int = 0
    board_source: str = "empty"
    pass_required: bool = True
    live_checked: bool = False
    live_configured: bool = False
    auto_ok: int = 0
    auto_warn: int = 0
    auto_fail: int = 0
    auto_skip: int = 0
    tcp_missing: int = 0
    tcp_resolved: int = 0
    tcp_rejected: int = 0
    live_error: str | None = None
    ebay_checked: bool = False
    ebay_configured: bool = False
    ebay_usable: bool = False
    ebay_ok: int = 0
    ebay_warn: int = 0
    ebay_fail: int = 0
    ebay_skip: int = 0
    ebay_error: str | None = None
    verdict_pass: int = 0
    verdict_review: int = 0
    verdict_fail: int = 0
    healed_n: int = 0
    healed_ids: list[str] = Field(default_factory=list)
    g0_ready: bool = False
    instructions: str
    items: list[SpotSniffItem] = Field(default_factory=list)


class SpotHealRequest(BaseModel):
    mode: Literal["dry_run", "null_market", "clear_history", "refetch"] = "dry_run"
    # High ceiling so one ops click can drain the desk (nightly uses unlimited).
    limit: int | None = Field(default=50, ge=1, le=5000)
    card_ids: list[str] | None = Field(
        default=None,
        description="Optional explicit card ids (reports / sniff). Skips cluster detect.",
        max_length=100,
    )


class SpotHealResponse(BaseModel):
    mode: str
    count: int = 0
    ids: list[str] = Field(default_factory=list)
    poison_keys: list[float] = Field(default_factory=list)
    nulled: int = 0
    history_cleared: int = 0
    quotes_quarantined: int = 0
    updated: int = 0
    skipped: int = 0
    skip_poison: int = 0
    skip_absurd: int = 0
    saved: int = 0


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
    ops: bool = False


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
    finishes: list[str] = Field(default_factory=list)
    finishes_source: str | None = None
    supertype: str | None = None
    price: float | None = None
    market_price: float | None = None
    predicted_price: float | None = None
    expected_change_pct: float | None = None
    expected_change_30d_pct: float | None = None
    price_change_3d_pct: float | None = None
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


class FxQuoteResponse(BaseModel):
    usd_eur: float
    as_of: str | None = None
    source: str = "fallback"
    fallback: bool = False


class IdentifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    limit: int = Field(default=8, ge=1, le=24)


class IdentifyMatch(BaseModel):
    score: float
    reasons: list[str] = Field(default_factory=list)
    card: CatalogCard


class IdentifyResponse(BaseModel):
    matches: list[IdentifyMatch] = Field(default_factory=list)
    total: int = 0
    source: Literal["supabase", "demo", "empty"] = "empty"
    name_hints: list[str] = Field(default_factory=list)
    number: str | None = None
    collector: str | None = None


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
    # Same series as /history — included so Soft Ink SSR skips a second round-trip.
    points: list[HistoryPoint] = Field(default_factory=list)
    explain: CardExplain = Field(default_factory=CardExplain)
    source: Literal["supabase", "demo", "empty"] = "empty"


class CardHistoryResponse(BaseModel):
    card_id: str
    points: list[HistoryPoint]
    stats: HistoryStats = Field(default_factory=HistoryStats)


class PsaGradeStats(BaseModel):
    has_history_series: bool = False
    period_key: str | None = None
    sales_count: int | float | None = None
    price_status: str | None = None
    last_sale_at: int | float | None = None
    price_expires_at: int | float | None = None
    price: float | None = None
    canonical: str | None = None


# Backward-compatible alias used by existing OpenAPI clients.
Psa10Stats = PsaGradeStats


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
    psa10_stats: PsaGradeStats = Field(default_factory=PsaGradeStats)
    psa9: list[HistoryPoint] = Field(default_factory=list)
    psa9_error: str | None = None
    psa9_stats: PsaGradeStats = Field(default_factory=PsaGradeStats)
    grades: Literal["none", "psa10", "all"] = "none"
    cache: Literal["hit", "miss"] | None = None


class SignalBoardResponse(BaseModel):
    buys: list[CatalogCard]
    sells: list[CatalogCard]
    holds: list[CatalogCard]
    source: Literal["supabase", "demo", "empty"] = "empty"


class MarketMover(BaseModel):
    id: str
    name: str
    set_name: str | None = None
    image_url: str | None = None
    price: float | None = None
    price_change_7d_pct: float | None = None
    signal: str | None = None


class MarketPulseResponse(BaseModel):
    """Landing desk pulse — sure band breadth + past-7d movers (not a Fear/Greed meter)."""

    source: Literal["supabase", "demo", "empty"] = "empty"
    board_total: int = 0
    sure_under: int = 0
    sure_over: int = 0
    signals: dict[str, int] = Field(default_factory=dict)
    median_change_7d_pct: float | None = None
    rising_n: int = 0
    falling_n: int = 0
    flat_n: int = 0
    observed_n: int = 0
    rising_share_pct: float | None = None
    risers: list[MarketMover] = Field(default_factory=list)
    fallers: list[MarketMover] = Field(default_factory=list)


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
    spot_source: str | None = None  # board | justtcg_variant | multiplier
    variant_id: str | None = None
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


class PortfolioBootstrapResponse(BaseModel):
    """One-shot portfolio desk payload (lots + watch + alerts)."""

    portfolio: PortfolioResponse
    watchlist: WatchlistResponse
    alerts: WatchAlertsResponse


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


class TrustStatus(BaseModel):
    allowed: bool
    reason: str = ""
    checkout_url: str | None = None


class TrustCalibration(BaseModel):
    rmse: float | None = None
    r2: float | None = None
    rmse_vs_naive: float | None = None
    direction_accuracy_pct: float | None = None
    direction_n: int | None = None
    conformal_q: float | None = None
    conformal_alpha: float | None = None
    conformal_width_cap: float | None = None
    wf_folds: int | None = None
    wf_direction_accuracy_pct: float | None = None
    wf_rmse_vs_naive: float | None = None


class TrustCoverage(BaseModel):
    method: str = "unavailable"
    target_pct: float = 80.0
    coverage_pct: float | None = None
    n: int = 0
    note: str = ""


class TrustRadarBacktest(BaseModel):
    lookback_days: int = 7
    horizon_days: int = 7
    n: int = 0
    hit_rate_pct: float | None = None
    avg_move_pct: float | None = None
    under_n: int = 0
    over_n: int = 0
    min_edge: float = 0.0
    method: str = "forward_tip_ledger"
    tighten_suggested: bool = False
    pending_n: int = 0
    coverage_pct: float | None = None
    coverage_n: int = 0
    note: str | None = None


class TrustResponse(BaseModel):
    source: Literal["supabase", "demo", "empty"] = "empty"
    trained_at: str | None = None
    artifact_id: str = "latest"
    horizon_days: int = 7
    min_edge: float = 0.0
    calibration: TrustCalibration = Field(default_factory=TrustCalibration)
    conformal_coverage: TrustCoverage = Field(default_factory=TrustCoverage)
    radar_backtest: TrustRadarBacktest = Field(default_factory=TrustRadarBacktest)


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


class RadarBootstrapResponse(BaseModel):
    """One-shot Radar desk payload (Pro status + board when allowed)."""

    status: RadarStatus
    board: RadarResponse | None = None


class RadarPreviewResponse(BaseModel):
    """Public teaser — top UNDER edges only (no Pro auth)."""

    forecast_days: int = 7
    under_total: int = 0
    underpriced: list[RadarCard] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"
    # True when share-safe desk was empty and we fell back to sure UNDER.
    relaxed: bool = False


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
    spot_source: str | None = None
    variant_id: str | None = None
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
    """Public share payload — live re-score plus Kestrel Pro CTA."""

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
    inventory_format: Literal["soft_ink", "tcgplayer", "generic"] = "generic"


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


class SealedQuoteItem(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    tcgplayer_id: str | None = None
    gtin: str | None = None
    spot_usd: float | None = None
    image_url: str | None = None
    source: str = "empty"
    kind: Literal["sealed"] = "sealed"
    ensured: bool | None = None
    demo: bool | None = None
    product_kind: str | None = None
    packs: int | None = None
    # Showcase teaser: product spot − Illustration Rare set sum (USD).
    ir_vs_product_usd: float | None = None


class SealedQuoteResponse(BaseModel):
    items: list[SealedQuoteItem] = Field(default_factory=list)
    source: Literal["justtcg", "demo", "empty"] = "empty"
    justtcg_configured: bool = False
    error: str | None = None


class SealedRarityGroup(BaseModel):
    key: str
    label: str
    count: int = 0
    total_usd: float = 0.0
    featured: list[CatalogCard] = Field(default_factory=list)


class SealedDetailSummary(BaseModel):
    ir_vs_product_usd: float | None = None
    sir_boxes: float | None = None


class SealedDetailResponse(BaseModel):
    product: SealedQuoteItem
    shelf: list[SealedQuoteItem] = Field(default_factory=list)
    hits: list[CatalogCard] = Field(default_factory=list)
    groups: list[SealedRarityGroup] = Field(default_factory=list)
    summary: SealedDetailSummary | None = None
    source: Literal["justtcg", "demo", "empty"] = "empty"
    justtcg_configured: bool = False
    set_name: str | None = None


class SealedEnsureRequest(BaseModel):
    card_id: str | None = None
    name: str
    set_name: str | None = None
    tcgplayer_id: str | None = None
    gtin: str | None = None
    spot_usd: float | None = None
    image_url: str | None = None
    source: str = "justtcg"


class BinderSetSummary(BaseModel):
    set_name: str
    set_id: str | None = None
    total: int = 0
    owned: int = 0
    missing: int = 0
    pct: float = 0.0
    missing_cost: float = 0.0


class BinderSetsResponse(BaseModel):
    sets: list[BinderSetSummary] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"
    demo: bool = False


class BinderMissingCard(BaseModel):
    id: str
    name: str
    number: str | None = None
    rarity: str | None = None
    price: float | None = None
    image_url: str | None = None


class BinderResponse(BaseModel):
    set_name: str
    set_id: str | None = None
    total: int = 0
    owned: int = 0
    missing: int = 0
    pct_complete: float = 0.0
    missing_cost: float = 0.0
    missing_unpriced: int = 0
    owned_ids: list[str] = Field(default_factory=list)
    missing_cards: list[BinderMissingCard] = Field(default_factory=list)
    source: Literal["supabase", "demo", "empty"] = "empty"
    demo: bool = False


class FunnelEventIn(BaseModel):
    event: str
    session: str | None = None
    props: dict[str, Any] | None = None


class FunnelBatchIn(BaseModel):
    events: list[FunnelEventIn] = Field(default_factory=list, max_length=20)


class FunnelBatchOut(BaseModel):
    accepted: int = 0
    rejected: int = 0


class FunnelSummaryResponse(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    recent: list[dict[str, Any]] = Field(default_factory=list)
    uptime_s: float = 0.0
    allowed_events: list[str] = Field(default_factory=list)
    persisted: bool = False
    source: str = "memory"


class TrialConversionResponse(BaseModel):
    """Ops: Creem trial → paid hygiene (M4.3) + G3 trust strip."""

    by_status: dict[str, int] = Field(default_factory=dict)
    active: int = 0
    trialing: int = 0
    canceled: int = 0
    expired: int = 0
    past_due: int = 0
    entitled: int = 0
    paid_share_pct: float | None = None
    webhook_outcomes: dict[str, Any] = Field(default_factory=dict)
    g3_trust: dict[str, Any] = Field(default_factory=dict)
    source: Literal["supabase", "empty"] = "empty"
