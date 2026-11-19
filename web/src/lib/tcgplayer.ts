/** US TCGplayer search deep-link — Soft Ink spots stay on the board; this is the US checkout path. */

export function tcgplayerSearchUrl(
  name: string,
  setName?: string | null,
): string {
  const q = [name, setName]
    .map((s) => String(s || "").trim())
    .filter(Boolean)
    .join(" ");
  const params = new URLSearchParams();
  params.set("q", q || name);
  params.set("productLineName", "pokemon");
  return `https://www.tcgplayer.com/search/pokemon/product?${params.toString()}`;
}
