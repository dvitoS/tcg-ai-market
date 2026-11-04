import type { PortfolioLot } from "@/lib/types";

export type PnlFilter = "all" | "up" | "down";
export type LotSort =
  | "name"
  | "value_desc"
  | "value_asc"
  | "pnl_desc"
  | "pnl_asc"
  | "qty_desc";

export type PortfolioGalleryFilters = {
  query: string;
  rarity: string;
  pnl: PnlFilter;
  sort: LotSort;
  minPrice?: number;
  maxPrice?: number;
};

function lotSpot(lot: PortfolioLot): number {
  return Number(lot.current_price ?? lot.market_price ?? lot.purchase_price ?? 0);
}

function lotValue(lot: PortfolioLot): number {
  return Number(lot.market_value ?? lotSpot(lot) * Number(lot.quantity || 0));
}

function lotPnl(lot: PortfolioLot): number {
  return Number(lot.pnl ?? 0);
}

export function uniqueLotRarities(lots: PortfolioLot[]): string[] {
  const set = new Set<string>();
  for (const lot of lots) {
    const rarity = String(lot.rarity || "").trim();
    if (rarity) set.add(rarity);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

export function filterPortfolioLots(
  lots: PortfolioLot[],
  filters: PortfolioGalleryFilters,
): PortfolioLot[] {
  const q = filters.query.trim().toLowerCase();
  let rows = lots.slice();

  if (q) {
    rows = rows.filter((lot) => {
      const name = String(lot.name || "").toLowerCase();
      const id = String(lot.card_id || "").toLowerCase();
      return name.includes(q) || id.includes(q);
    });
  }

  if (filters.rarity) {
    rows = rows.filter((lot) => String(lot.rarity || "") === filters.rarity);
  }

  if (filters.pnl === "up") {
    rows = rows.filter((lot) => lotPnl(lot) > 0);
  } else if (filters.pnl === "down") {
    rows = rows.filter((lot) => lotPnl(lot) < 0);
  }

  if (filters.minPrice != null) {
    rows = rows.filter((lot) => lotSpot(lot) >= filters.minPrice!);
  }
  if (filters.maxPrice != null) {
    rows = rows.filter((lot) => lotSpot(lot) <= filters.maxPrice!);
  }

  const sorted = rows.slice();
  switch (filters.sort) {
    case "value_desc":
      sorted.sort((a, b) => lotValue(b) - lotValue(a));
      break;
    case "value_asc":
      sorted.sort((a, b) => lotValue(a) - lotValue(b));
      break;
    case "pnl_desc":
      sorted.sort((a, b) => lotPnl(b) - lotPnl(a));
      break;
    case "pnl_asc":
      sorted.sort((a, b) => lotPnl(a) - lotPnl(b));
      break;
    case "qty_desc":
      sorted.sort((a, b) => Number(b.quantity || 0) - Number(a.quantity || 0));
      break;
    case "name":
    default:
      sorted.sort((a, b) =>
        String(a.name || a.card_id).localeCompare(String(b.name || b.card_id)),
      );
      break;
  }
  return sorted;
}
