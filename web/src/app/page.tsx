import { BrowseMarket } from "@/components/BrowseMarket";
import { fetchCatalog } from "@/lib/api";
import type { CatalogMeta } from "@/lib/types";

export const dynamic = "force-dynamic";

const EMPTY_META: CatalogMeta = {
  total: 0,
  sets: [],
  signals: {},
  price_min: 0,
  price_max: 100,
  source: "empty",
};

export default async function HomePage() {
  let items = [] as Awaited<ReturnType<typeof fetchCatalog>>["items"];
  let total = 0;
  let meta = EMPTY_META;
  let error: string | null = null;

  try {
    const data = await fetchCatalog({ mode: "browse", limit: 24, offset: 0 });
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
    />
  );
}
