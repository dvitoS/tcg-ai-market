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
