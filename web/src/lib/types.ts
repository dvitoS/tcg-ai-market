export type CatalogCard = {
  id: string;
  name: string;
  set_name?: string | null;
  rarity?: string | null;
  finishes?: string[];
  finishes_source?: string | null;
  supertype?: string | null;
  price?: number | null;
  market_price?: number | null;
  predicted_price?: number | null;
  expected_change_pct?: number | null;
  expected_change_30d_pct?: number | null;
  price_change_3d_pct?: number | null;
  price_change_7d_pct?: number | null;
  signal?: string | null;
  confidence_ok?: boolean;
  conformal_ok?: boolean;
  confidence_level?: string | null;
  history_points?: number;
  image_url?: string | null;
};

export type CatalogMeta = {
  total: number;
  sets: string[];
  signals: Record<string, number>;
  price_min: number;
  price_max: number;
  source: "supabase" | "demo" | "empty";
};

export type CatalogResponse = {
  items: CatalogCard[];
  total: number;
  limit: number;
  offset: number;
  meta: CatalogMeta;
};

export type CatalogMode = "browse" | "signals";

export type HistoryPoint = {
  date: string;
  price: number;
};

export type HistoryStats = {
  points: number;
  min_price?: number | null;
  max_price?: number | null;
  last_price?: number | null;
  previous_price?: number | null;
  day_change_pct?: number | null;
  first_date?: string | null;
  last_date?: string | null;
};

export type ExplainRow = {
  label: string;
  value: string;
};

export type CardExplain = {
  confidence_level: string;
  confidence_ok: boolean;
  confidence_reason: string;
  hold_band_pct: number;
  horizon_days: number;
  rows: ExplainRow[];
};

export type CardDetailResponse = {
  card: CatalogCard;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
  history: HistoryStats;
  /** Same series as /history — preferred for SSR so we skip a second fetch. */
  points?: HistoryPoint[];
  explain?: CardExplain;
  source: "supabase" | "demo" | "empty";
};

export type CardHistoryResponse = {
  card_id: string;
  points: HistoryPoint[];
  stats: HistoryStats;
};

export type CardPriceSourcesResponse = {
  card_id: string;
  name: string;
  set_name?: string | null;
  tcgplayer_id?: string | null;
  justtcg_configured: boolean;
  tcgplayer: HistoryPoint[];
  justtcg: HistoryPoint[];
  justtcg_fallback: boolean;
  justtcg_from_db?: boolean;
  justtcg_error?: string | null;
  psa10: HistoryPoint[];
  psa10_error?: string | null;
  psa10_stats: {
    has_history_series: boolean;
    period_key?: string | null;
    sales_count?: number | null;
    price_status?: string | null;
    last_sale_at?: number | null;
    price_expires_at?: number | null;
    price?: number | null;
    canonical?: string | null;
  };
  psa9?: HistoryPoint[];
  psa9_error?: string | null;
  psa9_stats?: {
    has_history_series: boolean;
    period_key?: string | null;
    sales_count?: number | null;
    price_status?: string | null;
    last_sale_at?: number | null;
    price_expires_at?: number | null;
    price?: number | null;
    canonical?: string | null;
  };
  grades?: "none" | "psa10" | "all";
  cache?: "hit" | "miss" | null;
};

export type IdentifyMatch = {
  score: number;
  reasons: string[];
  card: CatalogCard;
};

export type IdentifyResponse = {
  matches: IdentifyMatch[];
  total: number;
  source: "supabase" | "demo" | "empty";
  name_hints: string[];
  number?: string | null;
  collector?: string | null;
};

export type SealedQuoteItem = {
  card_id: string;
  name: string;
  set_name?: string | null;
  tcgplayer_id?: string | null;
  gtin?: string | null;
  spot_usd?: number | null;
  image_url?: string | null;
  source: string;
  kind: "sealed";
  ensured?: boolean | null;
  demo?: boolean | null;
};

export type SealedQuoteResponse = {
  items: SealedQuoteItem[];
  source: "justtcg" | "demo" | "empty";
  justtcg_configured: boolean;
  error?: string | null;
};

export type AuthUser = {
  id: string;
  email?: string | null;
  dev?: boolean;
  /** Soft Ink operator — System status / data-health. */
  ops?: boolean;
};

export type PortfolioLot = {
  id: number | string;
  card_id: string;
  quantity: number;
  purchase_price: number;
  purchase_date?: string | null;
  condition?: string | null;
  printing?: string | null;
  grade?: string | null;
  status?: string;
  sale_price?: number | null;
  sale_date?: string | null;
  name?: string | null;
  rarity?: string | null;
  set_name?: string | null;
  image_url?: string | null;
  nm_market_price?: number | null;
  price_factor?: number | null;
  spot_source?: string | null;
  variant_id?: string | null;
  market_price?: number | null;
  current_price?: number | null;
  invested?: number | null;
  market_value?: number | null;
  pnl?: number | null;
  pnl_pct?: number | null;
  signal?: string | null;
  expected_change_pct?: number | null;
  predicted_price?: number | null;
  outlook_value?: number | null;
  outlook_roi_pct?: number | null;
  outlook_lo_pct?: number | null;
  outlook_hi_pct?: number | null;
  outlook_conformal_ok?: boolean | null;
  outlook_horizon_days?: number | null;
  lot_action?: string | null;
  is_top_ai?: boolean | null;
};

export type PortfolioSummary = {
  lots: number;
  value: number;
  invested: number;
  pnl: number;
  pnl_pct: number;
  outlook_value: number;
  outlook_pct: number;
  outlook_horizon_days?: number;
};

export type PortfolioResponse = {
  items: PortfolioLot[];
  summary: PortfolioSummary;
  demo: boolean;
};

export type PortfolioPerfPoint = {
  date: string;
  invested: number;
  market_value: number;
  ai_fair_value?: number | null;
  ai_lo?: number | null;
  ai_hi?: number | null;
};

export type PortfolioDrawdownCallout = {
  peak_date: string;
  trough_date: string;
  drawdown_pct: number;
  peak_value: number;
  trough_value: number;
  trim_count: number;
  note: string;
};

export type PortfolioPerformanceResponse = {
  points: PortfolioPerfPoint[];
  days: number;
  demo: boolean;
  ai_fair_value?: number | null;
  ai_lo?: number | null;
  ai_hi?: number | null;
  drawdown_callouts?: PortfolioDrawdownCallout[];
};

export type WatchlistItem = {
  id?: number | string | null;
  card_id: string;
  created_at?: string | null;
  name?: string | null;
  rarity?: string | null;
  set_name?: string | null;
  image_url?: string | null;
  market_price?: number | null;
  signal?: string | null;
  expected_change_pct?: number | null;
  predicted_price?: number | null;
};

export type WatchlistResponse = {
  items: WatchlistItem[];
  demo: boolean;
};

export type WatchAlertItem = {
  card_id: string;
  name: string;
  expected_pct: number;
  price_change_pct?: number | null;
  signal?: string | null;
  price: number;
  reason: "ai" | "price" | "both" | string;
  conformal_ok: boolean;
  sure: boolean;
  body: string;
};

export type WatchAlertsResponse = {
  items: WatchAlertItem[];
  threshold_pct: number;
  sure_only: boolean;
  sure_only_allowed: boolean;
  watch_count: number;
  demo: boolean;
  source: "supabase" | "demo" | "empty";
};

export type PortfolioBootstrapResponse = {
  portfolio: PortfolioResponse;
  watchlist: WatchlistResponse;
  alerts: WatchAlertsResponse;
};

export type ScannerCard = CatalogCard & {
  current_price?: number | null;
  ai_target_price?: number | null;
  expected_roi_pct?: number | null;
};

export type ScannerResponse = {
  forecast_days: number;
  growth_floor: number;
  min_growth: number;
  scoped: number;
  opp_total: number;
  warn_total: number;
  sets: string[];
  rarities: string[];
  opportunities: ScannerCard[];
  warnings: ScannerCard[];
  source: "supabase" | "demo" | "empty";
};

export type RadarCard = CatalogCard & {
  side: "UNDER" | "OVER";
  edge_pct?: number | null;
  spot?: number | null;
  fair_price?: number | null;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
  current_price?: number | null;
  ai_target_price?: number | null;
  expected_roi_pct?: number | null;
};

export type RadarStatus = {
  allowed: boolean;
  reason: string;
  checkout_url?: string | null;
  forecast_days: number;
  edge_floor: number;
};

export type RadarResponse = {
  forecast_days: number;
  edge_floor: number;
  min_edge: number;
  scoped: number;
  sure_scoped: number;
  under_total: number;
  over_total: number;
  sets: string[];
  rarities: string[];
  underpriced: RadarCard[];
  overpriced: RadarCard[];
  source: "supabase" | "demo" | "empty";
};

export type RadarBootstrapResponse = {
  status: RadarStatus;
  board: RadarResponse | null;
};

export type RadarPreviewResponse = {
  forecast_days: number;
  under_total: number;
  underpriced: RadarCard[];
  source: "supabase" | "demo" | "empty";
};

export type MarketMover = {
  id: string;
  name: string;
  set_name?: string | null;
  image_url?: string | null;
  price?: number | null;
  price_change_7d_pct?: number | null;
  signal?: string | null;
};

export type MarketPulseResponse = {
  source: "supabase" | "demo" | "empty";
  board_total: number;
  sure_under: number;
  sure_over: number;
  signals: Record<string, number>;
  median_change_7d_pct?: number | null;
  rising_n: number;
  falling_n: number;
  flat_n: number;
  observed_n: number;
  rising_share_pct?: number | null;
  risers: MarketMover[];
  fallers: MarketMover[];
};

export type TrustCalibration = {
  rmse?: number | null;
  r2?: number | null;
  rmse_vs_naive?: number | null;
  direction_accuracy_pct?: number | null;
  direction_n?: number | null;
  conformal_q?: number | null;
  conformal_alpha?: number | null;
  conformal_width_cap?: number | null;
  wf_folds?: number | null;
  wf_direction_accuracy_pct?: number | null;
  wf_rmse_vs_naive?: number | null;
};

export type TrustCoverage = {
  method: string;
  target_pct: number;
  coverage_pct?: number | null;
  n: number;
  note: string;
};

export type TrustRadarBacktest = {
  lookback_days: number;
  horizon_days: number;
  n: number;
  hit_rate_pct?: number | null;
  avg_move_pct?: number | null;
  under_n: number;
  over_n: number;
  min_edge?: number;
  method: string;
  tighten_suggested?: boolean;
  pending_n?: number;
  coverage_pct?: number | null;
  coverage_n?: number;
  note?: string | null;
};

export type TrustResponse = {
  source: "supabase" | "demo" | "empty";
  trained_at?: string | null;
  artifact_id: string;
  horizon_days: number;
  min_edge?: number;
  calibration: TrustCalibration;
  conformal_coverage: TrustCoverage;
  radar_backtest: TrustRadarBacktest;
};

export type TradeLineIn = {
  card_id: string;
  quantity: number;
  condition?: string;
  printing?: string;
};

export type TradeLineOut = TradeLineIn & {
  matched: boolean;
  price_factor?: number;
  spot_source?: string | null;
  variant_id?: string | null;
  name?: string | null;
  set_name?: string | null;
  image_url?: string | null;
  spot?: number | null;
  fair_price?: number | null;
  expected_change_pct?: number | null;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
  signal?: string | null;
  conformal_ok: boolean;
  line_spot?: number | null;
  line_fair?: number | null;
};

export type TradeSide = {
  lines: TradeLineOut[];
  matched: number;
  unmatched: number;
  spot_total: number;
  fair_total: number;
  cards: number;
};

export type TradeStatus = {
  allowed: boolean;
  reason: string;
  checkout_url?: string | null;
  fair_band_pct: number;
};

export type TradeResponse = {
  you: TradeSide;
  them: TradeSide;
  net_spot_usd: number;
  net_fair_usd: number;
  net_spot_pct: number;
  net_fair_pct: number;
  spot_verdict: string;
  ai_verdict: string;
  verdict: string;
  fair_band_pct: number;
  source: "supabase" | "demo" | "empty";
};

export type TradeShareCreated = {
  id: string;
  path: string;
  url?: string | null;
};

export type TradeShareView = TradeResponse & {
  checkout_url?: string | null;
  share_id: string;
};

export type DealerStatus = {
  allowed: boolean;
  reason: string;
  checkout_url?: string | null;
  default_fee_pct: number;
  default_ship_usd: number;
  sample_csv: string;
  sample_tcgplayer_csv?: string;
  csv_hint?: string;
};

export type DealerRow = {
  card_id?: string | null;
  name?: string | null;
  set_name?: string | null;
  quantity: number;
  unit_cost?: number | null;
  matched: boolean;
  spot?: number | null;
  expected_change_pct?: number | null;
  signal?: string | null;
  conformal_ok: boolean;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
  net_now?: number | null;
  net_forecast?: number | null;
  net_edge_pct?: number | null;
  action: string;
  inventory_value?: number | null;
};

export type DealerResponse = {
  items: DealerRow[];
  rows: number;
  matched: number;
  actionable: number;
  unmatched: number;
  inventory_value: number;
  fee_pct: number;
  ship_usd: number;
  source: "supabase" | "demo" | "empty";
  demo: boolean;
  inventory_format?: "soft_ink" | "tcgplayer" | "generic";
};

export type EbayListing = {
  item_id?: string | null;
  title?: string | null;
  price?: number | null;
  currency?: string | null;
  condition?: string | null;
  url?: string | null;
  image?: string | null;
  seller?: string | null;
  sold_date?: string | null;
  comp_source?: string | null;
  is_sold?: boolean | null;
};

export type EbayCompsResponse = {
  card_id: string;
  configured: boolean;
  epn: boolean;
  listings: EbayListing[];
  listings_error?: string | null;
  sold: EbayListing[];
  sold_hint?: string | null;
  sold_stats: {
    min?: number | null;
    median?: number | null;
    max?: number | null;
    n: number;
    is_sold: boolean;
  };
  sold_fallback_active: boolean;
  active_fallback: EbayListing[];
};

export type DataHealthResponse = {
  live: number;
  db: number;
  empty: number;
  fallback: number;
  error: number;
  cache_hit: number;
  attempts: number;
  miss_or_fallback_pct: number;
  justtcg_configured: boolean;
  cards_total?: number;
  cards_with_history?: number;
  history_coverage_pct?: number;
  fresh_history_pct?: number | null;
  sure_rows?: number;
  quotes_total?: number;
  spot_quarantine_rows?: number;
  spot_poison_clusters?: number;
  spot_poison_cluster_sample?: Array<{
    price?: number;
    count?: number;
    sets?: number;
    rarities?: string[];
  }>;
  unmatched_sets_count?: number | null;
  unmatched_sets_sample?: Array<{ set_code?: string; set_name?: string }>;
  spot_qa_captured_at?: string | null;
  board_source?: string;
  nightly_slo_ok?: boolean | null;
  nightly_elapsed_s?: number | null;
  quotes_written?: number | null;
};

export type SpotSniffItem = {
  card_id: string;
  name: string;
  set_name?: string | null;
  rarity?: string | null;
  side: "UNDER" | "OVER";
  spot?: number | null;
  fair_price?: number | null;
  edge_pct?: number | null;
  tcgplayer_id?: string | null;
  tcgplayer_url?: string | null;
  kestrel_path: string;
  tcp_live?: number | null;
  tcp_delta_pct?: number | null;
  tcp_status?: "ok" | "warn" | "fail" | "skip";
  auto_status?: "ok" | "warn" | "fail" | "skip";
  tcp_resolved?: boolean;
  skip_reason?: string | null;
  ebay_median?: number | null;
  ebay_delta_pct?: number | null;
  ebay_n?: number;
  ebay_is_sold?: boolean;
  ebay_status?: "ok" | "warn" | "fail" | "skip";
  verdict?: "pass" | "review" | "fail";
  healed?: boolean;
  check_tcp?: boolean | null;
  check_ebay?: boolean | null;
  notes?: string;
};

export type SpotSniffPackResponse = {
  generated_at: string;
  limit: number;
  count: number;
  under_n: number;
  over_n: number;
  board_source: string;
  pass_required: boolean;
  live_checked?: boolean;
  live_configured?: boolean;
  auto_ok?: number;
  auto_warn?: number;
  auto_fail?: number;
  auto_skip?: number;
  tcp_missing?: number;
  tcp_resolved?: number;
  tcp_rejected?: number;
  live_error?: string | null;
  ebay_checked?: boolean;
  ebay_configured?: boolean;
  ebay_usable?: boolean;
  ebay_ok?: number;
  ebay_warn?: number;
  ebay_fail?: number;
  ebay_skip?: number;
  ebay_error?: string | null;
  verdict_pass?: number;
  verdict_review?: number;
  verdict_fail?: number;
  healed_n?: number;
  healed_ids?: string[];
  g0_ready?: boolean;
  instructions: string;
  items: SpotSniffItem[];
};

export type SpotHealMode =
  | "dry_run"
  | "null_market"
  | "clear_history"
  | "refetch";

export type SpotHealResponse = {
  mode: string;
  count: number;
  ids: string[];
  poison_keys: number[];
  nulled: number;
  history_cleared: number;
  quotes_quarantined?: number;
  updated: number;
  skipped: number;
  skip_poison: number;
  skip_absurd: number;
  saved: number;
};

export type BinderSetSummary = {
  set_name: string;
  set_id?: string | null;
  total: number;
  owned: number;
  missing: number;
  pct: number;
  missing_cost: number;
};

export type BinderSetsResponse = {
  sets: BinderSetSummary[];
  source: "supabase" | "demo" | "empty";
  demo: boolean;
};

export type BinderMissingCard = {
  id: string;
  name: string;
  number?: string | null;
  rarity?: string | null;
  price?: number | null;
  image_url?: string | null;
};

export type BinderResponse = {
  set_name: string;
  set_id?: string | null;
  total: number;
  owned: number;
  missing: number;
  pct_complete: number;
  missing_cost: number;
  missing_unpriced: number;
  owned_ids: string[];
  missing_cards: BinderMissingCard[];
  source: "supabase" | "demo" | "empty";
  demo: boolean;
};
