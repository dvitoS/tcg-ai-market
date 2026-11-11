import type {
  AuthUser,
  BinderResponse,
  BinderSetsResponse,
  CardDetailResponse,
  CardHistoryResponse,
  CardPriceSourcesResponse,
  CatalogMode,
  CatalogResponse,
  IdentifyResponse,
  DataHealthResponse,
  SpotHealMode,
  SpotHealResponse,
  SpotSniffPackResponse,
  DealerResponse,
  DealerStatus,
  EbayCompsResponse,
  MarketPulseResponse,
  RadarPreviewResponse,
  RadarResponse,
  RadarStatus,
  SealedQuoteItem,
  SealedQuoteResponse,
  TrustResponse,
  TradeLineIn,
  TradeResponse,
  TradeShareCreated,
  TradeShareView,
  TradeStatus,
  PortfolioBootstrapResponse,
  PortfolioLot,
  PortfolioPerformanceResponse,
  PortfolioResponse,
  RadarBootstrapResponse,
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

/** Prefer FastAPI `{ detail }` (string or list) over raw response bodies. */
export async function readApiError(
  res: Response,
  fallback: string,
): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return fallback;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    const detail = body?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg?: unknown }).msg || "");
          }
          return "";
        })
        .filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
  } catch {
    /* plain text */
  }
  const trimmed = text.trim();
  if (trimmed.startsWith("{") && trimmed.includes('"detail"')) {
    return fallback;
  }
  return trimmed || fallback;
}

export async function identifyFromOcrText(
  text: string,
  limit = 8,
): Promise<IdentifyResponse> {
  const res = await fetch(apiUrl("/api/identify"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    cache: "no-store",
    body: JSON.stringify({ text, limit }),
  });
  if (!res.ok) {
    throw new Error(`Identify failed (${res.status})`);
  }
  return res.json() as Promise<IdentifyResponse>;
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
  // Finishes / foil mode must not stick on a cold Soft Ink nav cache.
  const res = await fetch(apiUrl(`/api/cards/${encodeURIComponent(cardId)}`), {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.headers || {}),
    },
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

const _priceSourcesInflight = new Map<
  string,
  Promise<CardPriceSourcesResponse>
>();

export type PriceSourcesGrades = "none" | "psa10" | "all";

export async function fetchCardPriceSources(
  cardId: string,
  options: { limit?: number; grades?: PriceSourcesGrades } = {},
): Promise<CardPriceSourcesResponse> {
  const limit = options.limit ?? 180;
  const grades = options.grades ?? "none";
  const key = `${cardId}|${limit}|${grades}`;
  const existing = _priceSourcesInflight.get(key);
  if (existing) return existing;

  const promise = (async () => {
    const qs = new URLSearchParams({
      limit: String(limit),
      grades,
    });
    const res = await fetch(
      apiUrl(`/api/cards/${encodeURIComponent(cardId)}/sources?${qs}`),
      {
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
    if (!res.ok) {
      throw new Error(`Card price sources failed (${res.status})`);
    }
    return res.json() as Promise<CardPriceSourcesResponse>;
  })().finally(() => {
    _priceSourcesInflight.delete(key);
  });

  _priceSourcesInflight.set(key, promise);
  return promise;
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

export async function fetchPortfolioBootstrap(
  opts: {
    include_sold?: boolean;
    threshold_pct?: number;
    sure_only?: boolean;
    dismissed?: string[];
  } = {},
): Promise<PortfolioBootstrapResponse> {
  const params = new URLSearchParams();
  if (opts.include_sold != null) {
    params.set("include_sold", opts.include_sold ? "true" : "false");
  }
  if (opts.threshold_pct != null) {
    params.set("threshold_pct", String(opts.threshold_pct));
  }
  if (opts.sure_only != null) {
    params.set("sure_only", opts.sure_only ? "true" : "false");
  }
  if (opts.dismissed?.length) {
    params.set("dismissed", opts.dismissed.join(","));
  }
  const qs = params.toString();
  const res = await fetch(
    apiUrl(`/api/portfolio/bootstrap${qs ? `?${qs}` : ""}`),
    {
      headers: {
        Accept: "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(`Portfolio bootstrap failed (${res.status})`);
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

export async function fetchSealedQuote(input: {
  q?: string;
  tcgplayer_id?: string;
  gtin?: string;
  limit?: number;
}): Promise<SealedQuoteResponse> {
  const params = new URLSearchParams();
  if (input.q) params.set("q", input.q);
  if (input.tcgplayer_id) params.set("tcgplayer_id", input.tcgplayer_id);
  if (input.gtin) params.set("gtin", input.gtin);
  if (input.limit != null) params.set("limit", String(input.limit));
  const res = await fetch(apiUrl(`/api/sealed/quote?${params.toString()}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Sealed quote failed (${res.status})`);
  }
  return res.json();
}

export async function ensureSealedCard(
  body: SealedQuoteItem,
): Promise<SealedQuoteItem> {
  const res = await fetch(apiUrl("/api/sealed/ensure"), {
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
    throw new Error(detail || `Sealed ensure failed (${res.status})`);
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

export async function fetchMarketPulse(
  movers = 5,
  init?: RequestInit,
): Promise<MarketPulseResponse> {
  const res = await fetch(apiUrl(`/api/market/pulse?movers=${movers}`), {
    headers: { Accept: "application/json" },
    next: { revalidate: 60 },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Market pulse failed (${res.status})`);
  }
  return res.json();
}

export async function fetchRadarPreview(
  limit = 5,
  init?: RequestInit,
): Promise<RadarPreviewResponse> {
  const res = await fetch(apiUrl(`/api/radar/preview?limit=${limit}`), {
    headers: { Accept: "application/json" },
    // Short revalidate so landing /pro teaser can SSR without a cold no-store wait.
    next: { revalidate: 60 },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Radar preview failed (${res.status})`);
  }
  return res.json();
}

/** Deal of the Day — top UNDER edge(s) from the public radar preview. */
export async function fetchDealOfTheDay(
  limit = 1,
): Promise<RadarPreviewResponse> {
  return fetchRadarPreview(Math.max(1, Math.min(8, limit)));
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

export async function fetchRadarBootstrap(
  query: RadarQuery = {},
): Promise<RadarBootstrapResponse> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.set) params.set("set", query.set);
  if (query.rarity) params.set("rarity", query.rarity);
  if (query.min_price != null) params.set("min_price", String(query.min_price));
  if (query.max_price != null) params.set("max_price", String(query.max_price));
  if (query.min_edge != null) params.set("min_edge", String(query.min_edge));
  if (query.limit != null) params.set("limit", String(query.limit));
  const qs = params.toString();
  const res = await fetch(
    apiUrl(`/api/radar/bootstrap${qs ? `?${qs}` : ""}`),
    {
      headers: {
        Accept: "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(
      await readApiError(res, `Radar bootstrap failed (${res.status})`),
    );
  }
  return res.json();
}

export async function fetchTrustReport(input?: {
  horizon_days?: number;
  lookback_days?: number;
  sample_n?: number;
  min_edge?: number;
}): Promise<TrustResponse> {
  const params = new URLSearchParams();
  if (input?.horizon_days != null) {
    params.set("horizon_days", String(input.horizon_days));
  }
  if (input?.lookback_days != null) {
    params.set("lookback_days", String(input.lookback_days));
  }
  if (input?.sample_n != null) {
    params.set("sample_n", String(input.sample_n));
  }
  if (input?.min_edge != null) {
    params.set("min_edge", String(input.min_edge));
  }
  const qs = params.toString();
  const res = await fetch(apiUrl(`/api/trust${qs ? `?${qs}` : ""}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("TRUST_NOT_FOUND");
    }
    if (res.status === 401) {
      throw new Error("TRUST_AUTH");
    }
    if (res.status === 403) {
      throw new Error("TRUST_PRO");
    }
    throw new Error(await readApiError(res, `Trust report failed (${res.status})`));
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
    throw new Error(
      await readApiError(res, `Trade status failed (${res.status})`),
    );
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
    throw new Error(
      await readApiError(res, `Trade score failed (${res.status})`),
    );
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
    throw new Error(
      await readApiError(res, `Trade share failed (${res.status})`),
    );
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
    throw new Error(
      await readApiError(res, `Trade share not found (${res.status})`),
    );
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

export async function fetchBinderSets(): Promise<BinderSetsResponse> {
  const res = await fetch(apiUrl("/api/binder/sets"), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await readApiError(res, `Binder sets failed (${res.status})`);
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchBinder(input: {
  set_name: string;
  missing_limit?: number;
}): Promise<BinderResponse> {
  const params = new URLSearchParams();
  params.set("set_name", input.set_name);
  if (input.missing_limit != null) {
    params.set("missing_limit", String(input.missing_limit));
  }
  const res = await fetch(apiUrl(`/api/binder?${params.toString()}`), {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await readApiError(res, `Binder failed (${res.status})`);
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchDataHealth(): Promise<DataHealthResponse> {
  const res = await fetch(apiUrl("/api/data-health"), {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Data health failed (${res.status})`);
  }
  return res.json();
}

export type FunnelSummaryResponse = {
  counts: Record<string, number>;
  total: number;
  recent: Array<{
    event: string;
    session?: string | null;
    props?: Record<string, unknown> | null;
    ts?: number;
  }>;
  uptime_s: number;
  allowed_events: string[];
};

export async function fetchFunnelSummary(): Promise<FunnelSummaryResponse> {
  const res = await fetch(apiUrl("/api/funnel/summary"), {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Funnel summary failed (${res.status})`);
  }
  return res.json();
}

export type G3TrustSnapshot = {
  cancel_events: number;
  refund_events: number;
  cited_total: number;
  wrong_price_hits: number;
  wrong_price_pct: number | null;
  reason_buckets: Record<string, number>;
  entitled: number;
  canceled_entitlements: number;
  spot_reports_open: number;
  spot_reports_total: number;
  spot_reports_per_100_entitled: number | null;
  gate_target_pct: number;
  gate_ok: boolean;
  uptime_s: number;
};

export type TrialConversionResponse = {
  by_status: Record<string, number>;
  active: number;
  trialing: number;
  canceled: number;
  expired: number;
  past_due: number;
  entitled: number;
  paid_share_pct: number | null;
  webhook_outcomes: {
    counts?: Record<string, number>;
    uptime_s?: number;
  };
  g3_trust?: G3TrustSnapshot;
  source: "supabase" | "empty";
};

export async function fetchTrialConversion(): Promise<TrialConversionResponse> {
  const res = await fetch(apiUrl("/api/billing/conversion"), {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Trial conversion failed (${res.status})`);
  }
  return res.json();
}

export type SpotReportSummary = {
  counts: Record<string, number>;
  open_total: number;
  oldest_open_age_h: number | null;
  overdue_ack: number;
  overdue_heal: number;
  ack_sla_hours: number;
  heal_sla_hours: number;
  recent: Array<{
    id: string;
    card_id: string;
    note?: string | null;
    spot?: number | null;
    status: string;
    created_at: number;
  }>;
  uptime_s: number;
};

export async function reportWrongSpot(input: {
  card_id: string;
  note?: string;
  spot?: number | null;
  session?: string;
}): Promise<{ id: string; card_id: string; status: string }> {
  const res = await fetch(apiUrl("/api/spots/report"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    throw new Error(`Spot report failed (${res.status})`);
  }
  return res.json();
}

export async function fetchSpotReportSummary(): Promise<SpotReportSummary> {
  const res = await fetch(apiUrl("/api/spots/reports/summary"), {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Spot report summary failed (${res.status})`);
  }
  return res.json();
}

export async function fetchSpotSniffPack(
  limit = 20,
  opts?: { liveCheck?: boolean; ebayCheck?: boolean; autoHeal?: boolean },
): Promise<SpotSniffPackResponse> {
  const live = opts?.liveCheck !== false;
  const ebay = opts?.ebayCheck !== false;
  const heal = opts?.autoHeal !== false;
  const qs = new URLSearchParams({
    limit: String(Math.max(4, Math.min(40, limit))),
    live_check: live ? "true" : "false",
    ebay_check: ebay ? "true" : "false",
    auto_heal: heal ? "true" : "false",
  });
  const res = await fetch(apiUrl(`/api/data-health/sniff-pack?${qs}`), {
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Sniff pack failed (${res.status})`);
  }
  return res.json();
}

export async function resetDataHealth(): Promise<DataHealthResponse> {
  const res = await fetch(apiUrl("/api/data-health/reset"), {
    method: "POST",
    headers: { Accept: "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Data health reset failed (${res.status})`);
  }
  return res.json();
}

export async function healPoisonedSpots(input: {
  mode: SpotHealMode;
  limit?: number;
  cardIds?: string[];
}): Promise<SpotHealResponse> {
  const res = await fetch(apiUrl("/api/data-health/heal-spots"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      mode: input.mode,
      limit: input.limit ?? 50,
      ...(input.cardIds?.length ? { card_ids: input.cardIds } : {}),
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await readApiError(res, `Spot heal failed (${res.status})`);
    throw new Error(detail);
  }
  return res.json();
}

export async function healAutoUnsafeSpots(input: {
  mode?: SpotHealMode;
  limit?: number;
}): Promise<SpotHealResponse> {
  const res = await fetch(apiUrl("/api/data-health/heal-auto-unsafe"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      mode: input.mode ?? "null_market",
      limit: input.limit ?? 5000,
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await readApiError(
      res,
      `Auto-quarantine failed (${res.status})`,
    );
    throw new Error(detail);
  }
  return res.json();
}

/** Drain auto-unsafe + poison clusters until clean (replaces 10-at-a-time Heal clicks). */
export async function sweepDeskPoison(): Promise<SpotHealResponse> {
  const res = await fetch(apiUrl("/api/data-health/desk-sweep"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: "{}",
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await readApiError(res, `Desk sweep failed (${res.status})`);
    throw new Error(detail);
  }
  return res.json();
}

export async function healOpenSpotReports(input: {
  mode: SpotHealMode;
  limit?: number;
}): Promise<SpotHealResponse> {
  const mode = encodeURIComponent(input.mode);
  const limit = Math.max(1, Math.min(100, input.limit ?? 30));
  const res = await fetch(
    apiUrl(`/api/spots/reports/heal-open?mode=${mode}&limit=${limit}`),
    {
      method: "POST",
      headers: { Accept: "application/json", ...authHeaders() },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const detail = await readApiError(res, `Heal-open failed (${res.status})`);
    throw new Error(detail);
  }
  return res.json();
}
