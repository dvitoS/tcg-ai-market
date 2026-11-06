/** EU Cardmarket deep-links — Soft Ink spots stay USD; this is the EU checkout path. */

export function cardmarketSearchUrl(
  name: string,
  setName?: string | null,
): string {
  const q = [name, setName].map((s) => String(s || "").trim()).filter(Boolean).join(" ");
  const params = new URLSearchParams();
  params.set("searchString", q || name);
  return `https://www.cardmarket.com/en/Pokemon/Products/Search?${params.toString()}`;
}
