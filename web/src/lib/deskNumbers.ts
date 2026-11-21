/**
 * Shared Market / AI fair / price-gap for Soft Ink desks (T1.2).
 *
 * Detail hero, DOTD, and Radar paste must agree on these three numbers.
 * Ranking / model ``edge_pct`` (pred_lo) stays separate — never pass it as the
 * user-facing “difference” when we have spot + good.
 */

export type DeskNumberInput = {
  price?: number | null;
  spot?: number | null;
  lastPrice?: number | null;
  predicted_price?: number | null;
  fair_price?: number | null;
  side?: string | null;
};

export type DeskNumbers = {
  asking: number | null;
  good: number | null;
  /** (good − asking) / asking × 100 — same as detail hero gapPct. */
  edgeGapPct: number | null;
  /** UNDER when good > asking, OVER when good < asking, else null. */
  side: "UNDER" | "OVER" | null;
};

function finite(n: unknown): number | null {
  if (n == null) return null;
  const v = typeof n === "number" ? n : Number(n);
  return Number.isFinite(v) ? v : null;
}

export function resolveDeskNumbers(input: DeskNumberInput): DeskNumbers {
  const asking =
    finite(input.lastPrice) ?? finite(input.spot) ?? finite(input.price);
  const good = finite(input.fair_price) ?? finite(input.predicted_price);

  let edgeGapPct: number | null = null;
  if (asking != null && asking > 0 && good != null) {
    edgeGapPct = ((good - asking) / asking) * 100;
  }

  let side: DeskNumbers["side"] = null;
  const hint = String(input.side || "").toUpperCase();
  if (hint === "UNDER" || hint === "OVER") {
    side = hint;
  } else if (edgeGapPct != null) {
    if (edgeGapPct > 0.5) side = "UNDER";
    else if (edgeGapPct < -0.5) side = "OVER";
  }

  return { asking, good, edgeGapPct, side };
}
