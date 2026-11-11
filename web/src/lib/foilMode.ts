/** Soft Ink foil mode from catalog finish labels + rarity fallback. */

export type FoilMode = "holo" | "reverse" | null;

const HOLO_NEEDLES = [
  "holofoil",
  "cosmos",
  "rainbow",
  "amazing",
  "etched",
  "gold",
  "foil",
];

export function foilModeFromFinishes(
  finishes: string[] | null | undefined,
): FoilMode {
  const labels = (finishes || [])
    .map((f) => String(f || "").trim().toLowerCase())
    .filter(Boolean);
  if (!labels.length) return null;

  const hasReverse = labels.some((f) => f.includes("reverse"));
  const hasHolo = labels.some((f) => {
    if (f.includes("reverse")) return false;
    return HOLO_NEEDLES.some((n) => f.includes(n));
  });

  // Prefer art-window holo when both printings exist.
  if (hasHolo) return "holo";
  if (hasReverse) return "reverse";
  return null;
}

/** Last-resort hint when finishes array is empty (cold Soft Ink nav). */
export function foilModeFromRarity(rarity: string | null | undefined): FoilMode {
  const text = String(rarity || "")
    .trim()
    .toLowerCase();
  if (!text) return null;
  if (text.includes("reverse")) return "reverse";
  // SV+ desk labels (Double / Ultra Rare) are foil even without "holo" in the string.
  if (
    text.includes("holo") ||
    text.includes("foil") ||
    text.includes("rainbow") ||
    text.includes("amazing") ||
    text.includes("illustration") ||
    text.includes("hyper") ||
    text.includes("secret") ||
    text.includes("ultra rare") ||
    text.includes("double rare") ||
    text.includes("shiny") ||
    text.includes("radiant") ||
    text.includes("ace spec")
  ) {
    return "holo";
  }
  return null;
}

/** Name cue for chase foils when rarity is Promo / blank. */
export function foilModeFromName(name: string | null | undefined): FoilMode {
  const text = String(name || "")
    .trim()
    .toLowerCase();
  if (!text) return null;
  if (
    /\b(ex|gx|v|vmax|vstar)\b/.test(text) ||
    text.includes("lv.x") ||
    text.includes("lv. x")
  ) {
    return "holo";
  }
  return null;
}

export function resolveFoilMode(
  finishes: string[] | null | undefined,
  rarity?: string | null,
  name?: string | null,
): FoilMode {
  return (
    foilModeFromFinishes(finishes) ||
    foilModeFromRarity(rarity) ||
    foilModeFromName(name)
  );
}
