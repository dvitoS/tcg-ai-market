/** Soft Ink foil mode from catalog finish labels. */

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
