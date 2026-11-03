import type { CatalogMode, CatalogResponse } from "./types";

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

export function formatMoney(value?: number | null, currency = "USD"): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatChange(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}
