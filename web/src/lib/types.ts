export type CatalogCard = {
  id: string;
  name: string;
  set_name?: string | null;
  rarity?: string | null;
  supertype?: string | null;
  price?: number | null;
  market_price?: number | null;
  predicted_price?: number | null;
  expected_change_pct?: number | null;
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

export type CardDetailResponse = {
  card: CatalogCard;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
  history: HistoryStats;
  source: "supabase" | "demo" | "empty";
};

export type CardHistoryResponse = {
  card_id: string;
  points: HistoryPoint[];
  stats: HistoryStats;
};

export type AuthUser = {
  id: string;
  email?: string | null;
  dev?: boolean;
};

export type PortfolioLot = {
  id: number | string;
  card_id: string;
  quantity: number;
  purchase_price: number;
  purchase_date?: string | null;
  condition?: string | null;
  grade?: string | null;
  status?: string;
  name?: string | null;
  rarity?: string | null;
  set_name?: string | null;
  image_url?: string | null;
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
};

export type PortfolioSummary = {
  lots: number;
  value: number;
  invested: number;
  pnl: number;
  pnl_pct: number;
  outlook_value: number;
  outlook_pct: number;
};

export type PortfolioResponse = {
  items: PortfolioLot[];
  summary: PortfolioSummary;
  demo: boolean;
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

export type DealerStatus = {
  allowed: boolean;
  reason: string;
  checkout_url?: string | null;
  default_fee_pct: number;
  default_ship_usd: number;
  sample_csv: string;
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
