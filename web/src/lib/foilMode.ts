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
  if (
    text.includes("holo") ||
    text.includes("foil") ||
    text.includes("rainbow") ||
    text.includes("amazing") ||
    text.includes("illustration") ||
    text.includes("hyper") ||
    text.includes("secret")
  ) {
    return "holo";
  }
  return null;
}

export function resolveFoilMode(
  finishes: string[] | null | undefined,
  rarity?: string | null,
): FoilMode {
  return foilModeFromFinishes(finishes) || foilModeFromRarity(rarity);
}
