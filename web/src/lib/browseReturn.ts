/** Remember last Soft Ink browse URL so card detail can return to the same search. */

export const BROWSE_RETURN_KEY = "kestrel_browse_return";

export function saveBrowseReturn(pathWithQuery: string): void {
  if (typeof window === "undefined") return;
  const next = String(pathWithQuery || "").trim();
  if (!next.startsWith("/browse")) return;
  try {
    sessionStorage.setItem(BROWSE_RETURN_KEY, next);
  } catch {
    /* private mode / quota */
  }
}

export function readBrowseReturn(fallback = "/browse"): string {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = sessionStorage.getItem(BROWSE_RETURN_KEY) || "";
    if (raw.startsWith("/browse")) return raw;
  } catch {
    /* ignore */
  }
  return fallback;
}

export function buildBrowseHref(parts: {
  q?: string;
  set?: string;
  signal?: string;
  min?: string;
  max?: string;
  mode?: string;
}): string {
  const params = new URLSearchParams();
  const q = (parts.q || "").trim();
  const set = (parts.set || "").trim();
  const signal = (parts.signal || "").trim();
  const min = (parts.min || "").trim();
  const max = (parts.max || "").trim();
  const mode = (parts.mode || "").trim();
  if (q) params.set("q", q);
  if (set) params.set("set", set);
  if (signal) params.set("signal", signal);
  if (min) params.set("min", min);
  if (max) params.set("max", max);
  if (mode && mode !== "browse") params.set("mode", mode);
  const qs = params.toString();
  return qs ? `/browse?${qs}` : "/browse";
}
