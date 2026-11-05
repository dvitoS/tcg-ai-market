/** Client-only Kestrel Radar filter share (`?share=`). */

export type RadarShareFilters = {
  q?: string;
  set?: string;
  rarity?: string;
  min_edge?: number;
  min_price?: number;
  max_price?: number;
};

type RadarSharePayload = RadarShareFilters & { v: 1 };

function toBase64Url(raw: string): string {
  const b64 =
    typeof btoa === "function"
      ? btoa(raw)
      : Buffer.from(raw, "utf8").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(token: string): string {
  const b64 = token.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4));
  const padded = b64 + pad;
  if (typeof atob === "function") return atob(padded);
  return Buffer.from(padded, "base64").toString("utf8");
}

function cleanText(value: unknown, max = 80): string | undefined {
  if (typeof value !== "string") return undefined;
  const text = value.trim().slice(0, max);
  return text || undefined;
}

function cleanNum(value: unknown, { min = 0, max = 1e9 } = {}): number | undefined {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n < min || n > max) return undefined;
  return n;
}

export function encodeRadarShare(filters: RadarShareFilters): string {
  const payload: RadarSharePayload = { v: 1 };
  const q = cleanText(filters.q);
  const set = cleanText(filters.set, 120);
  const rarity = cleanText(filters.rarity, 60);
  const minEdge = cleanNum(filters.min_edge, { min: 0, max: 100 });
  const minPrice = cleanNum(filters.min_price);
  const maxPrice = cleanNum(filters.max_price);
  if (q) payload.q = q;
  if (set) payload.set = set;
  if (rarity) payload.rarity = rarity;
  if (minEdge != null) payload.min_edge = minEdge;
  if (minPrice != null) payload.min_price = minPrice;
  if (maxPrice != null) payload.max_price = maxPrice;
  return toBase64Url(JSON.stringify(payload));
}

export function decodeRadarShare(token: string | null | undefined): RadarShareFilters | null {
  if (!token || typeof token !== "string") return null;
  try {
    const raw = fromBase64Url(token.trim());
    const data = JSON.parse(raw) as Partial<RadarSharePayload>;
    if (data?.v !== 1 || typeof data !== "object") return null;
    const out: RadarShareFilters = {};
    const q = cleanText(data.q);
    const set = cleanText(data.set, 120);
    const rarity = cleanText(data.rarity, 60);
    const minEdge = cleanNum(data.min_edge, { min: 0, max: 100 });
    const minPrice = cleanNum(data.min_price);
    const maxPrice = cleanNum(data.max_price);
    if (q) out.q = q;
    if (set) out.set = set;
    if (rarity) out.rarity = rarity;
    if (minEdge != null) out.min_edge = minEdge;
    if (minPrice != null) out.min_price = minPrice;
    if (maxPrice != null) out.max_price = maxPrice;
    return out;
  } catch {
    return null;
  }
}

export function buildRadarShareUrl(
  origin: string,
  filters: RadarShareFilters,
): string {
  const token = encodeRadarShare(filters);
  const base = origin.replace(/\/$/, "");
  return `${base}/radar?share=${encodeURIComponent(token)}`;
}
