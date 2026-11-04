import type { DealerRow } from "@/lib/types";

export const DEALER_CSV_COLUMNS = [
  "action",
  "name",
  "card_id",
  "set_name",
  "quantity",
  "unit_cost",
  "spot",
  "expected_change_pct",
  "net_edge_pct",
  "conformal_ok",
  "pred_lo_pct",
  "pred_hi_pct",
  "matched",
  "net_now",
  "net_forecast",
  "inventory_value",
] as const;

export function csvEscape(value: string | number | boolean | null | undefined): string {
  if (value == null) return "";
  const raw = String(value);
  if (/[",\n\r]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

export function dealerRowsToCsv(rows: DealerRow[]): string {
  const header = DEALER_CSV_COLUMNS.join(",");
  const lines = rows.map((row) =>
    DEALER_CSV_COLUMNS.map((key) =>
      csvEscape(row[key] as string | number | boolean | null | undefined),
    ).join(","),
  );
  return [header, ...lines].join("\n");
}

export function downloadDealerCsv(rows: DealerRow[], filename: string) {
  if (typeof window === "undefined" || rows.length === 0) return;
  const blob = new Blob([dealerRowsToCsv(rows)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
