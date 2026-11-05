/** Raw → PSA 10 grading EV (mirrors services/grading_ev.py). */

export const DEFAULT_GRADE_FEE_USD = 25;
export const DEFAULT_SHIP_USD = 15;
export const DEFAULT_SELL_FEE_PCT = 13;
export const DEFAULT_PSA9_RATIO = 0.45;

export type GradingSide = {
  exit_usd: number | null;
  proceeds_usd: number | null;
  net_usd: number | null;
  roi_pct: number | null;
};

export type GradingEvResult = {
  raw_usd: number | null;
  psa10_usd: number | null;
  psa9_usd: number | null;
  grade_fee_usd: number;
  ship_usd: number;
  sell_fee_pct: number;
  psa9_ratio: number;
  all_in_usd: number | null;
  breakeven_psa10_usd: number | null;
  psa10: GradingSide;
  psa9: GradingSide;
  ready: boolean;
};

export function computeGradingEv(input: {
  rawUsd?: number | null;
  psa10Usd?: number | null;
  gradeFeeUsd?: number;
  shipUsd?: number;
  sellFeePct?: number;
  psa9Ratio?: number;
}): GradingEvResult {
  const fee = Math.max(0, Number(input.gradeFeeUsd ?? DEFAULT_GRADE_FEE_USD));
  const ship = Math.max(0, Number(input.shipUsd ?? DEFAULT_SHIP_USD));
  const sell = Math.max(
    0,
    Math.min(100, Number(input.sellFeePct ?? DEFAULT_SELL_FEE_PCT)),
  );
  const ratio = Math.max(
    0,
    Math.min(1, Number(input.psa9Ratio ?? DEFAULT_PSA9_RATIO)),
  );

  let raw =
    input.rawUsd != null && Number.isFinite(input.rawUsd)
      ? Number(input.rawUsd)
      : null;
  let psa10 =
    input.psa10Usd != null && Number.isFinite(input.psa10Usd)
      ? Number(input.psa10Usd)
      : null;
  if (raw != null && raw < 0) raw = null;
  if (psa10 != null && psa10 < 0) psa10 = null;

  const allIn = raw != null ? raw + fee + ship : null;
  const netMult = 1 - sell / 100;

  function side(exit: number | null): GradingSide {
    if (exit == null || allIn == null || netMult <= 0) {
      return {
        exit_usd: exit,
        proceeds_usd: null,
        net_usd: null,
        roi_pct: null,
      };
    }
    const proceeds = exit * netMult;
    const net = proceeds - allIn;
    const roi = allIn > 0 ? (net / allIn) * 100 : null;
    return {
      exit_usd: exit,
      proceeds_usd: proceeds,
      net_usd: net,
      roi_pct: roi,
    };
  }

  const psa9 = psa10 != null ? psa10 * ratio : null;
  const breakeven =
    allIn != null && netMult > 0 ? allIn / netMult : null;

  return {
    raw_usd: raw,
    psa10_usd: psa10,
    psa9_usd: psa9,
    grade_fee_usd: fee,
    ship_usd: ship,
    sell_fee_pct: sell,
    psa9_ratio: ratio,
    all_in_usd: allIn,
    breakeven_psa10_usd: breakeven,
    psa10: side(psa10),
    psa9: side(psa9),
    ready: raw != null && psa10 != null,
  };
}
