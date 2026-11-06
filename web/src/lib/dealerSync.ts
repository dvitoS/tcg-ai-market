/** Persist dealer inventory CSV locally so Soft Ink reopens with last sync. */

export type DealerSyncPayload = {
  csvText: string;
  feePct: number;
  shipUsd: number;
  savedAt: string;
  format?: string;
};

const KEY_PREFIX = "kestrel_dealer_inventory_v1:";

export function dealerSyncKey(userId: string | null | undefined): string {
  return `${KEY_PREFIX}${userId || "anon"}`;
}

export function readDealerSync(
  userId: string | null | undefined,
): DealerSyncPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(dealerSyncKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DealerSyncPayload;
    if (!parsed?.csvText || typeof parsed.csvText !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeDealerSync(
  userId: string | null | undefined,
  payload: Omit<DealerSyncPayload, "savedAt"> & { savedAt?: string },
): void {
  if (typeof window === "undefined") return;
  try {
    const body: DealerSyncPayload = {
      csvText: payload.csvText,
      feePct: payload.feePct,
      shipUsd: payload.shipUsd,
      format: payload.format,
      savedAt: payload.savedAt || new Date().toISOString(),
    };
    window.localStorage.setItem(dealerSyncKey(userId), JSON.stringify(body));
  } catch {
    /* quota / private mode */
  }
}

export function clearDealerSync(userId: string | null | undefined): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(dealerSyncKey(userId));
  } catch {
    /* ignore */
  }
}
