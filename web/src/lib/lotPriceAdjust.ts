/** Condition / printing multipliers on NM board spots (mirrors services/lot_price_adjust.py). */

export const RAW_CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"] as const;
export const PRINTINGS = ["Normal", "Reverse", "Holo"] as const;

export type RawCondition = (typeof RAW_CONDITIONS)[number];
export type Printing = (typeof PRINTINGS)[number];

const CONDITION_MULT: Record<RawCondition, number> = {
  NM: 1,
  LP: 0.85,
  MP: 0.7,
  HP: 0.5,
  DMG: 0.3,
};

const PRINTING_MULT: Record<Printing, number> = {
  Normal: 1,
  Reverse: 1.05,
  Holo: 1.1,
};

export function normalizeCondition(value?: string | null): RawCondition {
  const text = String(value || "NM").trim().toUpperCase();
  if ((RAW_CONDITIONS as readonly string[]).includes(text)) {
    return text as RawCondition;
  }
  return "NM";
}

export function normalizePrinting(value?: string | null): Printing {
  const raw = String(value || "Normal").trim().toLowerCase();
  if (raw === "reverse" || raw === "reverse holo" || raw === "reverseholo") {
    return "Reverse";
  }
  if (raw === "holo" || raw === "holofoil" || raw === "foil") {
    return "Holo";
  }
  if (raw === "normal" || raw === "nonfoil" || raw === "non-foil" || !raw) {
    return "Normal";
  }
  const titled = raw.charAt(0).toUpperCase() + raw.slice(1);
  if ((PRINTINGS as readonly string[]).includes(titled)) {
    return titled as Printing;
  }
  return "Normal";
}

export function lotPriceFactor(input?: {
  condition?: string | null;
  printing?: string | null;
}): number {
  const c = normalizeCondition(input?.condition);
  const p = normalizePrinting(input?.printing);
  return CONDITION_MULT[c] * PRINTING_MULT[p];
}

export function adjustNmPrice(
  nmSpot?: number | null,
  input?: { condition?: string | null; printing?: string | null },
): number | null {
  if (nmSpot == null || !Number.isFinite(Number(nmSpot))) return null;
  return Number(nmSpot) * lotPriceFactor(input);
}
