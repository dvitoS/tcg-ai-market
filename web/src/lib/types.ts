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
