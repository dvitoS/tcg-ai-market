"use client";

import type { SensitivityPoint } from "@/lib/gradingEv";

type Props = {
  points: SensitivityPoint[];
  breakevenUsd?: number | null;
  spotPsa10Usd?: number | null;
  labelNet: string;
  labelExit: string;
};

export function GradingSensitivityChart({
  points,
  breakevenUsd,
  spotPsa10Usd,
  labelNet,
  labelExit,
}: Props) {
  if (points.length < 2) return null;

  const width = 360;
  const height = 140;
  const padX = 12;
  const padY = 14;
  const nets = points.map((p) => p.net_usd);
  const exits = points.map((p) => p.psa10_usd);
  const minNet = Math.min(...nets, 0);
  const maxNet = Math.max(...nets, 0);
  const minExit = Math.min(...exits);
  const maxExit = Math.max(...exits);
  const netSpan = Math.max(1e-6, maxNet - minNet);
  const exitSpan = Math.max(1e-6, maxExit - minExit);

  const xOf = (exit: number) =>
    padX + ((exit - minExit) / exitSpan) * (width - padX * 2);
  const yOf = (net: number) =>
    padY + (1 - (net - minNet) / netSpan) * (height - padY * 2);

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${xOf(p.psa10_usd).toFixed(1)},${yOf(p.net_usd).toFixed(1)}`)
    .join(" ");
  const zeroY = yOf(0);
  const beX =
    breakevenUsd != null && Number.isFinite(breakevenUsd)
      ? xOf(Number(breakevenUsd))
      : null;
  const spotX =
    spotPsa10Usd != null && Number.isFinite(spotPsa10Usd)
      ? xOf(Number(spotPsa10Usd))
      : null;

  return (
    <div className="grade-ev-chart" role="img" aria-label={`${labelNet} vs ${labelExit}`}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height}>
        <line
          className="grade-ev-chart-zero"
          x1={padX}
          x2={width - padX}
          y1={zeroY}
          y2={zeroY}
        />
        {beX != null ? (
          <line
            className="grade-ev-chart-be"
            x1={beX}
            x2={beX}
            y1={padY}
            y2={height - padY}
          />
        ) : null}
        {spotX != null ? (
          <line
            className="grade-ev-chart-spot"
            x1={spotX}
            x2={spotX}
            y1={padY}
            y2={height - padY}
          />
        ) : null}
        <path className="grade-ev-chart-line" d={path} fill="none" />
      </svg>
      <div className="grade-ev-chart-legend">
        <span>{labelExit}</span>
        <span>{labelNet}</span>
      </div>
    </div>
  );
}
