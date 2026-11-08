import { ImageResponse } from "next/og";

import { apiUrl } from "@/lib/api";
import { OG_SIZE, OgShell } from "@/lib/og";
import type { TradeShareView } from "@/lib/types";

export const alt = "Kestrel trade report";
export const size = OG_SIZE;
export const contentType = "image/png";

async function loadShare(shareId: string): Promise<TradeShareView | null> {
  const id = encodeURIComponent(shareId).replace(/%2F/gi, "/");
  try {
    const res = await fetch(apiUrl(`/api/trade/share/${id}`), {
      headers: { Accept: "application/json" },
      next: { revalidate: 120 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TradeShareView;
  } catch {
    return null;
  }
}

function money(value?: number | null): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return `$${Number(value).toFixed(2)}`;
}

function pct(value?: number | null): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function verdictLabel(verdict: string): string {
  const key = (verdict || "").toUpperCase();
  if (key === "YOU_AHEAD") return "You ahead";
  if (key === "THEM_AHEAD") return "Them ahead";
  return "Fair trade";
}

function verdictColor(verdict: string): string {
  const key = (verdict || "").toUpperCase();
  if (key === "YOU_AHEAD") return "#7dcea0";
  if (key === "THEM_AHEAD") return "#e08a7a";
  return "#e0b483";
}

export default async function TradeShareOpenGraphImage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const shareId = decodeURIComponent(id || "").trim();
  const share = shareId ? await loadShare(shareId) : null;
  const verdict = share?.verdict || "FAIR";
  const label = verdictLabel(verdict);
  const color = verdictColor(verdict);
  const youSpot = money(share?.you?.spot_total);
  const themSpot = money(share?.them?.spot_total);
  const netFair = pct(share?.net_fair_pct);
  const band = share?.fair_band_pct != null ? `±${share.fair_band_pct}%` : "±band";

  return new ImageResponse(
    (
      <OgShell footer="kestreltcg.app/trade">
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 22,
            width: "100%",
          }}
        >
          <div
            style={{
              fontSize: 22,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#9a9288",
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            Trade report
          </div>
          <div
            style={{
              fontSize: 64,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              fontWeight: 650,
              color,
            }}
          >
            {label}
          </div>
          <div
            style={{
              display: "flex",
              gap: 36,
              marginTop: 8,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>You give (spot)</div>
              <div style={{ fontSize: 36, color: "#f7f1e8", fontWeight: 650 }}>
                {youSpot}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>They give (spot)</div>
              <div style={{ fontSize: 36, color: "#f7f1e8", fontWeight: 650 }}>
                {themSpot}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>
                Net sure fair · band {band}
              </div>
              <div style={{ fontSize: 36, color: "#e0b483", fontWeight: 650 }}>
                {netFair}
              </div>
            </div>
          </div>
          <div
            style={{
              marginTop: 10,
              fontSize: 22,
              color: "#9a9288",
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            Desk call, not financial advice · open on Kestrel Pro
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
