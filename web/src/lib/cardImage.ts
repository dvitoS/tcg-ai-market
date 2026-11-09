/**
 * Soft Ink card art helpers.
 *
 * Server already prefers TCGdex for known-broken pokemontcg CDN sets. This
 * client map covers warm caches / older payloads and img onError recovery.
 */

const BROKEN_POKEMONTCG_SETS = new Set([
  "me55",
  "me55c",
  "me2pt5",
  "me1",
  "me2",
  "me3",
  "me4",
  "me5",
  "me6",
]);

/** Keep in sync with tcgdex_client._SET_MAP (CAT.2a). */
const SET_MAP: Record<
  string,
  { setId: string; serie: string; pad: number }
> = {
  me1: { setId: "me01", serie: "me", pad: 3 },
  me2: { setId: "me02", serie: "me", pad: 3 },
  me3: { setId: "me03", serie: "me", pad: 3 },
  me4: { setId: "me04", serie: "me", pad: 3 },
  me5: { setId: "me05", serie: "me", pad: 3 },
  me6: { setId: "me06", serie: "me", pad: 3 },
  me2pt5: { setId: "me02.5", serie: "me", pad: 3 },
  me55: { setId: "30th", serie: "me", pad: 3 },
  sv1: { setId: "sv01", serie: "sv", pad: 3 },
  sv2: { setId: "sv02", serie: "sv", pad: 3 },
  sv3: { setId: "sv03", serie: "sv", pad: 3 },
  sv3pt5: { setId: "sv03.5", serie: "sv", pad: 3 },
  sv4: { setId: "sv04", serie: "sv", pad: 3 },
  sv4pt5: { setId: "sv04.5", serie: "sv", pad: 3 },
  sv5: { setId: "sv05", serie: "sv", pad: 3 },
  sv6: { setId: "sv06", serie: "sv", pad: 3 },
  sv6pt5: { setId: "sv06.5", serie: "sv", pad: 3 },
  sv7: { setId: "sv07", serie: "sv", pad: 3 },
  sv8: { setId: "sv08", serie: "sv", pad: 3 },
  sv8pt5: { setId: "sv08.5", serie: "sv", pad: 3 },
  sv9: { setId: "sv09", serie: "sv", pad: 3 },
  sv10: { setId: "sv10", serie: "sv", pad: 3 },
  zsv10pt5: { setId: "sv10.5b", serie: "sv", pad: 3 },
  rsv10pt5: { setId: "sv10.5w", serie: "sv", pad: 3 },
};

function padLocalId(number: string, width: number): string {
  const raw = String(number || "").trim();
  if (!raw) return raw;
  if (/^\d+$/.test(raw)) return raw.padStart(width, "0");
  const m = raw.match(/^([A-Za-z]+)(\d+)$/);
  if (m) return `${m[1]}${m[2].padStart(width, "0")}`;
  return raw;
}

export function tcgdexImageUrl(cardId: string): string | null {
  const id = String(cardId || "").trim();
  const dash = id.lastIndexOf("-");
  if (dash <= 0) return null;
  const setCode = id.slice(0, dash);
  const number = id.slice(dash + 1);
  const mapped = SET_MAP[setCode];
  if (!mapped) return null;
  const local = padLocalId(number, mapped.pad);
  return `https://assets.tcgdex.net/en/${mapped.serie}/${mapped.setId}/${local}/high.webp`;
}

export function resolveCardImageUrl(
  cardId: string | null | undefined,
  existing?: string | null,
): string {
  const id = String(cardId || "").trim();
  const url = String(existing || "").trim();
  const setCode = id.includes("-") ? id.slice(0, id.lastIndexOf("-")) : "";
  const tcgdex = id ? tcgdexImageUrl(id) : null;
  const broken =
    BROKEN_POKEMONTCG_SETS.has(setCode) ||
    (url.includes("images.pokemontcg.io/") &&
      [...BROKEN_POKEMONTCG_SETS].some((s) => url.includes(`/${s}/`)));
  if (tcgdex && (!url || broken)) return tcgdex;
  return url || tcgdex || "/kestrel-logo.png";
}

/** img onError: try TCGdex once, then Soft Ink mark. */
export function onCardImageError(
  event: { currentTarget: HTMLImageElement },
  cardId?: string | null,
): void {
  const img = event.currentTarget;
  const tried = img.dataset.tcgdexTried === "1";
  if (!tried && cardId) {
    const alt = tcgdexImageUrl(cardId);
    if (alt && img.src !== alt) {
      img.dataset.tcgdexTried = "1";
      img.src = alt;
      return;
    }
  }
  if (!img.src.includes("kestrel-logo")) {
    img.src = "/kestrel-logo.png";
  }
}
