/** eBay Completed+Sold search — Soft Ink sold comps never deep-link raw /itm alone. */

export function ebaySoldSearchUrl(
  name: string,
  setName?: string | null,
): string | null {
  const q = [name, setName]
    .map((s) => String(s || "").trim())
    .filter(Boolean)
    .join(" ")
    .slice(0, 140);
  if (!q) return null;
  const params = new URLSearchParams();
  params.set("_nkw", q);
  params.set("LH_Sold", "1");
  params.set("LH_Complete", "1");
  params.set("rt", "nc");
  params.set("_sop", "13");
  return `https://www.ebay.com/sch/i.html?${params.toString()}`;
}
