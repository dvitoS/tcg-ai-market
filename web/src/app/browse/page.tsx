import type { Metadata } from "next";

import { BrowseMarket } from "@/components/BrowseMarket";
import { fetchCatalog } from "@/lib/api";
import { absoluteUrl } from "@/lib/seo";
import type { CatalogMeta, CatalogMode } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Browse Pokémon TCG prices",
  description:
    "Browse live Pokémon TCG spot prices, Kestrel fair bands, and AI signals.",
  alternates: { canonical: absoluteUrl("/browse") },
};

const EMPTY_META: CatalogMeta = {
  total: 0,
  sets: [],
  signals: {},
  price_min: 0,
  price_max: 100,
  source: "empty",
};

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(
  value: string | string[] | undefined,
): string {
  if (Array.isArray(value)) return String(value[0] || "").trim();
  return String(value || "").trim();
}

export default async function BrowsePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const q = first(sp.q);
  const setName = first(sp.set);
  const signal = first(sp.signal);
  const min = first(sp.min);
  const max = first(sp.max);
  const modeRaw = first(sp.mode).toLowerCase();
  const mode: CatalogMode = modeRaw === "signals" ? "signals" : "browse";

  let items = [] as Awaited<ReturnType<typeof fetchCatalog>>["items"];
  let total = 0;
  let meta = EMPTY_META;
  let error: string | null = null;

  const minPrice = min ? Number(min) : undefined;
  const maxPrice = max ? Number(max) : undefined;

  try {
    const data = await fetchCatalog({
      mode,
      limit: 24,
      offset: 0,
      q: q || undefined,
      set: setName || undefined,
      signal: mode === "signals" ? signal || undefined : undefined,
      min_price:
        minPrice != null && Number.isFinite(minPrice) ? minPrice : undefined,
      max_price:
        maxPrice != null && Number.isFinite(maxPrice) ? maxPrice : undefined,
      sort: mode === "signals" ? "change_desc" : "price_desc",
    });
    items = data.items;
    total = data.total;
    meta = data.meta;
  } catch (err) {
    error =
      err instanceof Error
        ? `${err.message}. Start the API: PYTHONPATH=. uvicorn api.main:app --port 8000`
        : "Failed to reach Kestrel API";
  }

  return (
    <BrowseMarket
      initialItems={items}
      initialTotal={total}
      initialMeta={meta}
      initialError={error}
      initialQuery={q}
      initialSet={setName}
      initialSignal={signal}
      initialMin={min}
      initialMax={max}
      initialMode={mode}
    />
  );
}
