import { ImageResponse } from "next/og";

import { OG_SIZE, OgShell } from "@/lib/og";

export const alt = "Kestrel Radar";
export const size = OG_SIZE;
export const contentType = "image/png";

export default async function RadarOpenGraphImage() {
  return new ImageResponse(
    (
      <OgShell footer="kestreltcg.app/radar">
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
            Kestrel Radar
          </div>
          <div
            style={{
              fontSize: 58,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              fontWeight: 650,
              color: "#f7f1e8",
            }}
          >
            Sure UNDER / OVER vs the fair band
          </div>
          <div
            style={{
              display: "flex",
              gap: 28,
              marginTop: 8,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
                padding: "14px 20px",
                borderRadius: 12,
                border: "1px solid rgba(125, 206, 160, 0.35)",
                background: "rgba(125, 206, 160, 0.08)",
              }}
            >
              <div style={{ fontSize: 18, color: "#9a9288" }}>UNDER</div>
              <div style={{ fontSize: 32, color: "#7dcea0", fontWeight: 650 }}>
                Spot below sure fair
              </div>
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
                padding: "14px 20px",
                borderRadius: 12,
                border: "1px solid rgba(224, 138, 122, 0.35)",
                background: "rgba(224, 138, 122, 0.08)",
              }}
            >
              <div style={{ fontSize: 18, color: "#9a9288" }}>OVER</div>
              <div style={{ fontSize: 32, color: "#e08a7a", fontWeight: 650 }}>
                Spot above sure fair
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
