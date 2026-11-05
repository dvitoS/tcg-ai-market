/** Raw → PSA 10 grading EV (mirrors services/grading_ev.py). */

export const DEFAULT_GRADE_FEE_USD = 25;
export const DEFAULT_SHIP_USD = 15;
export const DEFAULT_SELL_FEE_PCT = 13;
export const DEFAULT_PSA9_RATIO = 0.45;

export type GradeFeePresetId =
  | "psa_value"
  | "psa_regular"
  | "psa_express"
  | "cgc_standard"
  | "custom";

export type GradeFeePreset = {
  id: GradeFeePresetId;
  gradeFeeUsd: number;
  shipUsd: number;
};

export const GRADE_FEE_PRESETS: GradeFeePreset[] = [
  { id: "psa_value", gradeFeeUsd: 19, shipUsd: 15 },
  { id: "psa_regular", gradeFeeUsd: 25, shipUsd: 15 },
  { id: "psa_express", gradeFeeUsd: 50, shipUsd: 20 },
  { id: "cgc_standard", gradeFeeUsd: 20, shipUsd: 15 },
];

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
  psa9_source: "live" | "ratio" | "none";
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

export type SensitivityPoint = {
  psa10_usd: number;
  net_usd: number;
};

export function computeGradingEv(input: {
  rawUsd?: number | null;
  psa10Usd?: number | null;
  psa9Usd?: number | null;
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
  let livePsa9 =
    input.psa9Usd != null && Number.isFinite(input.psa9Usd)
      ? Number(input.psa9Usd)
      : null;
  if (raw != null && raw < 0) raw = null;
  if (psa10 != null && psa10 < 0) psa10 = null;
  if (livePsa9 != null && livePsa9 < 0) livePsa9 = null;

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

  let psa9: number | null;
  let psa9Source: GradingEvResult["psa9_source"];
  if (livePsa9 != null) {
    psa9 = livePsa9;
    psa9Source = "live";
  } else if (psa10 != null) {
    psa9 = psa10 * ratio;
    psa9Source = "ratio";
  } else {
    psa9 = null;
    psa9Source = "none";
  }

  const breakeven =
    allIn != null && netMult > 0 ? allIn / netMult : null;

  return {
    raw_usd: raw,
    psa10_usd: psa10,
    psa9_usd: psa9,
    psa9_source: psa9Source,
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

export function gradingSensitivity(input: {
  rawUsd?: number | null;
  gradeFeeUsd?: number;
  shipUsd?: number;
  sellFeePct?: number;
  centerPsa10Usd?: number | null;
  steps?: number;
  span?: number;
}): SensitivityPoint[] {
  const steps = Math.max(3, Math.min(Number(input.steps ?? 21), 61));
  const span = Math.max(0.1, Math.min(Number(input.span ?? 0.5), 0.9));
  const base = computeGradingEv({
    rawUsd: input.rawUsd,
    psa10Usd: input.centerPsa10Usd,
    gradeFeeUsd: input.gradeFeeUsd,
    shipUsd: input.shipUsd,
    sellFeePct: input.sellFeePct,
  });
  let center = input.centerPsa10Usd;
  if (center == null || !Number.isFinite(center) || center <= 0) {
    center = base.breakeven_psa10_usd;
  }
  if (center == null || center <= 0) return [];

  const lo = center * (1 - span);
  const hi = center * (1 + span);
  if (hi <= lo) return [];

  const out: SensitivityPoint[] = [];
  for (let i = 0; i < steps; i += 1) {
    const t = i / (steps - 1);
    const exitPx = lo + (hi - lo) * t;
    const side = computeGradingEv({
      rawUsd: input.rawUsd,
      psa10Usd: exitPx,
      gradeFeeUsd: input.gradeFeeUsd,
      shipUsd: input.shipUsd,
      sellFeePct: input.sellFeePct,
    }).psa10;
    if (side.net_usd == null) continue;
    out.push({
      psa10_usd: Number(exitPx.toFixed(4)),
      net_usd: Number(side.net_usd.toFixed(4)),
    });
  }
  return out;
}

export function matchFeePreset(
  fee: number,
  ship: number,
): GradeFeePresetId {
  const hit = GRADE_FEE_PRESETS.find(
    (p) => p.gradeFeeUsd === fee && p.shipUsd === ship,
  );
  return hit?.id ?? "custom";
}
