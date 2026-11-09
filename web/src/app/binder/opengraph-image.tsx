import { ImageResponse } from "next/og";

import { OG_SIZE, OgShell } from "@/lib/og";

export const alt = "Kestrel binder";
export const size = OG_SIZE;
export const contentType = "image/png";

export default async function BinderOpenGraphImage() {
  return new ImageResponse(
    (
      <OgShell footer="kestreltcg.app/binder">
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
            Kestrel binder
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
            Set completion — owned, missing, buy-cost
          </div>
          <div
            style={{
              display: "flex",
              gap: 28,
              marginTop: 8,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>Owned</div>
              <div style={{ fontSize: 32, color: "#f7f1e8", fontWeight: 650 }}>
                Checklist
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>Missing</div>
              <div style={{ fontSize: 32, color: "#e0b483", fontWeight: 650 }}>
                Gaps
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 18, color: "#9a9288" }}>Buy-cost</div>
              <div style={{ fontSize: 32, color: "#7dcea0", fontWeight: 650 }}>
                To finish
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
            Shared links never include private P&amp;L
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
