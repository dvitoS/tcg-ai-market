/** Local recent search queries for Soft Ink search boxes. */

const PREFIX = "kestrel_search_recent_";
const MAX = 8;

export function readRecentSearches(scope: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(`${PREFIX}${scope}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((v) => String(v || "").trim())
      .filter(Boolean)
      .slice(0, MAX);
  } catch {
    return [];
  }
}

export function pushRecentSearch(scope: string, query: string): string[] {
  const q = query.trim();
  if (!q || typeof window === "undefined") return readRecentSearches(scope);
  const next = [q, ...readRecentSearches(scope).filter((x) => x.toLowerCase() !== q.toLowerCase())].slice(
    0,
    MAX,
  );
  try {
    window.localStorage.setItem(`${PREFIX}${scope}`, JSON.stringify(next));
  } catch {
    /* ignore quota */
  }
  return next;
}
