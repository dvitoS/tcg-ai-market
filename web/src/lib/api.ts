import type {
  AuthUser,
  CardDetailResponse,
  CardHistoryResponse,
  CardPriceSourcesResponse,
  CatalogMode,
  CatalogResponse,
  DataHealthResponse,
  DealerResponse,
  DealerStatus,
  EbayCompsResponse,
  RadarPreviewResponse,
  RadarResponse,
  RadarStatus,
  TradeLineIn,
  TradeResponse,
  TradeShareCreated,
  TradeShareView,
  TradeStatus,
  PortfolioLot,
  PortfolioPerformanceResponse,
  PortfolioResponse,
  ScannerResponse,
  WatchAlertsResponse,
  WatchlistResponse,
} from "./types";

const TOKEN_KEY = "kestrel_access_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (!token) window.localStorage.removeItem(TOKEN_KEY);
  else window.localStorage.setItem(TOKEN_KEY, token);
}

function authHeaders(token?: string | null): HeadersInit {
  const value = token === undefined ? getAccessToken() : token;
  return value ? { Authorization: `Bearer ${value}` } : {};
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export type CatalogQuery = {
  q?: string;
  set?: string;
  signal?: string;
  min_price?: number;
  max_price?: number;
  mode?: CatalogMode;
  limit?: number;
  offset?: number;
  sort?: "price_desc" | "price_asc" | "change_desc" | "change_asc" | "name";
};

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function fetchCatalog(
  query: CatalogQuery = {},
  init?: RequestInit,
): Promise<CatalogResponse> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.set) params.set("set", query.set);
  if (query.signal) params.set("signal", query.signal);
  if (query.min_price != null) params.set("min_price", String(query.min_price));
  if (query.max_price != null) params.set("max_price", String(query.max_price));
  if (query.mode) params.set("mode", query.mode);
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  if (query.sort) params.set("sort", query.sort);

  const url = apiUrl(`/api/catalog?${params.toString()}`);
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers || {}),
    },
    next: { revalidate: 30 },
  });
  if (!res.ok) {
    throw new Error(`Catalog request failed (${res.status})`);
  }
  return res.json() as Promise<CatalogResponse>;
}

export function formatMoney(
  value?: number | null,
  currency = "USD",
  digits = 2,
): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatChange(value?: number | null, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export async function fetchCardDetail(
  cardId: string,
  init?: RequestInit,
): Promise<CardDetailResponse> {
  const res = await fetch(apiUrl(`/api/cards/${encodeURIComponent(cardId)}`), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers || {}),
    },
    next: { revalidate: 30 },
  });
  if (res.status === 404) {
    throw new Error("NOT_FOUND");
  }
  if (!res.ok) {
    throw new Error(`Card detail failed (${res.status})`);
  }
  return res.json() as Promise<CardDetailResponse>;
}

export async function fetchCardHistory(
  cardId: string,
  limit = 180,
  init?: RequestInit,
): Promise<CardHistoryResponse> {
  const res = await fetch(
    apiUrl(`/api/cards/${encodeURIComponent(cardId)}/history?limit=${limit}`),
    {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.headers || {}),
      },
      next: { revalidate: 30 },
    },
  );
  if (!res.ok) {
    throw new Error(`Card history failed (${res.status})`);
  }
  return res.json() as Promise<CardHistoryResponse>;
}

export async function fetchCardPriceSources(
  cardId: string,
  limit = 180,
): Promise<CardPriceSourcesResponse> {
  const res = await fetch(
    apiUrl(`/api/cards/${encodeURIComponent(cardId)}/sources?limit=${limit}`),
    {
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(`Card price sources failed (${res.status})`);
  }
  return res.json() as Promise<CardPriceSourcesResponse>;
}

export async function fetchEbayComps(
  cardId: string,
  limit = 8,
): Promise<EbayCompsResponse> {
  const res = await fetch(
    apiUrl(`/api/cards/${encodeURIComponent(cardId)}/ebay?limit=${limit}`),
    {
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(`eBay comps failed (${res.status})`);
  }
  return res.json();
}

export async function loginRequest(
  email: string,
  password: string,
): Promise<{ access_token: string; user: AuthUser }> {
  const res = await fetch(apiUrl("/api/auth/login"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error("Invalid email or password");
  }
  return res.json();
}

export type SignupResult = {
  needs_confirmation: boolean;
  access_token?: string | null;
  refresh_token?: string | null;
  user?: AuthUser | null;
  message?: string | null;
};

export async function signupRequest(
  email: string,
  password: string,
): Promise<SignupResult> {
  const res = await fetch(apiUrl("/api/auth/signup"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let detail = "Could not create account";
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function forgotPasswordRequest(
  email: string,
  redirectTo?: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(apiUrl("/api/auth/forgot-password"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      redirect_to: redirectTo || undefined,
    }),
  });
  if (!res.ok) {
    let detail = "Could not start password reset";
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function updatePasswordRequest(
  password: string,
  opts: { accessToken: string; refreshToken?: string | null } ,
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(apiUrl("/api/auth/update-password"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${opts.accessToken}`,
    },
    body: JSON.stringify({
      password,
      refresh_token: opts.refreshToken || undefined,
    }),
  });
  if (!res.ok) {
    let detail = "Could not update password";
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchMe(token?: string | null): Promise<{
  authenticated: boolean;
  user: AuthUser | null;
}> {
  const res = await fetch(apiUrl("/api/auth/me"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(token),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    return { authenticated: false, user: null };
  }
  return res.json();
}

export async function fetchPortfolio(
  opts: { include_sold?: boolean } = {},
): Promise<PortfolioResponse> {
  const params = new URLSearchParams();
  if (opts.include_sold) params.set("include_sold", "true");
  const qs = params.toString();
  const res = await fetch(apiUrl(`/api/portfolio${qs ? `?${qs}` : ""}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Portfolio failed (${res.status})`);
  }
  return res.json();
}

export async function fetchPortfolioPerformance(
  opts: { max_days?: number } = {},
): Promise<PortfolioPerformanceResponse> {
  const params = new URLSearchParams();
  if (opts.max_days) params.set("max_days", String(opts.max_days));
  const qs = params.toString();
  const res = await fetch(
    apiUrl(`/api/portfolio/performance${qs ? `?${qs}` : ""}`),
    {
      headers: {
        Accept: "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(`Portfolio performance failed (${res.status})`);
  }
  return res.json();
}

export async function addPortfolioLot(body: {
  card_id: string;
  quantity: number;
  purchase_price: number;
  condition?: string;
  printing?: string;
  grade?: string | null;
  purchase_date?: string | null;
}): Promise<PortfolioLot> {
  const res = await fetch(apiUrl("/api/portfolio/lots"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Could not add lot (${res.status})`);
  }
  return res.json();
}

export async function updatePortfolioLot(
  entryId: number | string,
  body: {
    quantity?: number;
    purchase_price?: number;
    condition?: string;
    printing?: string;
    grade?: string | null;
    purchase_date?: string | null;
  },
): Promise<PortfolioLot> {
  const res = await fetch(apiUrl(`/api/portfolio/lots/${entryId}`), {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Could not update lot (${res.status})`);
  }
  return res.json();
}

export async function sellPortfolioLot(
  entryId: number | string,
  body: { sale_price: number; sale_date?: string | null },
): Promise<PortfolioLot> {
  const res = await fetch(apiUrl(`/api/portfolio/lots/${entryId}/sell`), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Could not sell lot (${res.status})`);
  }
  return res.json();
}

export async function deletePortfolioLot(entryId: number | string): Promise<void> {
  const res = await fetch(apiUrl(`/api/portfolio/lots/${entryId}`), {
    method: "DELETE",
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
  });
  if (!res.ok) {
    throw new Error(`Could not remove lot (${res.status})`);
  }
}

export type BillingStatus = {
  pro_open: boolean;
  checkout_url: string | null;
};

export type BillingMe = {
  pro_open: boolean;
  is_pro: boolean;
  reason: string;
  checkout_url: string | null;
  portal_url: string | null;
  authenticated: boolean;
  email?: string | null;
  enforcement_ready?: boolean;
};

export async function fetchBillingStatus(): Promise<BillingStatus> {
  const res = await fetch(apiUrl("/api/billing/status"), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Billing status failed (${res.status})`);
  }
  return res.json();
}

export async function fetchBillingMe(): Promise<BillingMe> {
  const res = await fetch(apiUrl("/api/billing/me"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Billing me failed (${res.status})`);
  }
  return res.json();
}

export async function fetchWatchlist(): Promise<WatchlistResponse> {
  const res = await fetch(apiUrl("/api/watchlist"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Watchlist failed (${res.status})`);
  }
  return res.json();
}

export async function addWatchlistCard(cardId: string): Promise<void> {
  const res = await fetch(apiUrl("/api/watchlist"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ card_id: cardId }),
  });
  if (!res.ok) {
    throw new Error(`Could not add watch (${res.status})`);
  }
}

export async function removeWatchlistCard(cardId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/watchlist/${encodeURIComponent(cardId)}`), {
    method: "DELETE",
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
  });
  if (!res.ok) {
    throw new Error(`Could not remove watch (${res.status})`);
  }
}

export async function fetchWatchStatus(cardId: string): Promise<boolean> {
  const res = await fetch(
    apiUrl(`/api/watchlist/${encodeURIComponent(cardId)}/status`),
    {
      headers: {
        Accept: "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );
  if (!res.ok) return false;
  const body = (await res.json()) as { watched?: boolean };
  return Boolean(body.watched);
}

export type WatchAlertsQuery = {
  threshold_pct?: number;
  sure_only?: boolean;
  dismissed?: string[];
};

export async function fetchWatchlistAlerts(
  query: WatchAlertsQuery = {},
): Promise<WatchAlertsResponse> {
  const params = new URLSearchParams();
  if (query.threshold_pct != null) {
    params.set("threshold_pct", String(query.threshold_pct));
  }
  if (query.sure_only != null) {
    params.set("sure_only", query.sure_only ? "true" : "false");
  }
  if (query.dismissed?.length) {
    params.set("dismissed", query.dismissed.join(","));
  }
  const qs = params.toString();
  const res = await fetch(apiUrl(`/api/watchlist/alerts${qs ? `?${qs}` : ""}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Watchlist alerts failed (${res.status})`);
  }
  return res.json();
}

export type ScannerQuery = {
  q?: string;
  set?: string;
  rarity?: string;
  min_price?: number;
  max_price?: number;
  min_growth?: number;
  limit?: number;
};

export async function fetchScanner(query: ScannerQuery = {}): Promise<ScannerResponse> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.set) params.set("set", query.set);
  if (query.rarity) params.set("rarity", query.rarity);
  if (query.min_price != null) params.set("min_price", String(query.min_price));
  if (query.max_price != null) params.set("max_price", String(query.max_price));
  if (query.min_growth != null) params.set("min_growth", String(query.min_growth));
  if (query.limit != null) params.set("limit", String(query.limit));
  const res = await fetch(apiUrl(`/api/scanner?${params.toString()}`), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Scanner failed (${res.status})`);
  }
  return res.json();
}

export async function fetchDealerStatus(): Promise<DealerStatus> {
  const res = await fetch(apiUrl("/api/dealer/status"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Dealer status failed (${res.status})`);
  }
  return res.json();
}

export type RadarQuery = {
  q?: string;
  set?: string;
  rarity?: string;
  min_price?: number;
  max_price?: number;
  min_edge?: number;
  limit?: number;
};

export async function fetchRadarPreview(
  limit = 5,
): Promise<RadarPreviewResponse> {
  const res = await fetch(apiUrl(`/api/radar/preview?limit=${limit}`), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Radar preview failed (${res.status})`);
  }
  return res.json();
}

export async function fetchRadarStatus(): Promise<RadarStatus> {
  const res = await fetch(apiUrl("/api/radar/status"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Radar status failed (${res.status})`);
  }
  return res.json();
}

export async function fetchRadar(query: RadarQuery = {}): Promise<RadarResponse> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.set) params.set("set", query.set);
  if (query.rarity) params.set("rarity", query.rarity);
  if (query.min_price != null) params.set("min_price", String(query.min_price));
  if (query.max_price != null) params.set("max_price", String(query.max_price));
  if (query.min_edge != null) params.set("min_edge", String(query.min_edge));
  if (query.limit != null) params.set("limit", String(query.limit));
  const res = await fetch(apiUrl(`/api/radar?${params.toString()}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Radar failed (${res.status})`);
  }
  return res.json();
}

export async function fetchTradeStatus(): Promise<TradeStatus> {
  const res = await fetch(apiUrl("/api/trade/status"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Trade status failed (${res.status})`);
  }
  return res.json();
}

export async function scoreTrade(input: {
  you: TradeLineIn[];
  them: TradeLineIn[];
  fair_band_pct?: number;
}): Promise<TradeResponse> {
  const res = await fetch(apiUrl("/api/trade/score"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Trade score failed (${res.status})`);
  }
  return res.json();
}

export async function createTradeShare(input: {
  you: TradeLineIn[];
  them: TradeLineIn[];
  fair_band_pct?: number;
}): Promise<TradeShareCreated> {
  const res = await fetch(apiUrl("/api/trade/share"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Trade share failed (${res.status})`);
  }
  return res.json();
}

export async function fetchTradeShare(shareId: string): Promise<TradeShareView> {
  const id = encodeURIComponent(shareId).replace(/%2F/gi, "/");
  const res = await fetch(apiUrl(`/api/trade/share/${id}`), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Trade share not found (${res.status})`);
  }
  return res.json();
}

export async function scoreDealerCsv(input: {
  csv_text: string;
  fee_pct: number;
  ship_usd: number;
}): Promise<DealerResponse> {
  const res = await fetch(apiUrl("/api/dealer/score"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Dealer score failed (${res.status})`);
  }
  return res.json();
}

export async function fetchDataHealth(): Promise<DataHealthResponse> {
  const res = await fetch(apiUrl("/api/data-health"), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Data health failed (${res.status})`);
  }
  return res.json();
}

export async function resetDataHealth(): Promise<DataHealthResponse> {
  const res = await fetch(apiUrl("/api/data-health/reset"), {
    method: "POST",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Data health reset failed (${res.status})`);
  }
  return res.json();
}
