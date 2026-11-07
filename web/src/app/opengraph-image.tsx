import { ImageResponse } from "next/og";

import { OG_SIZE, OgShell } from "@/lib/og";

export const alt = "Kestrel — Pokémon TCG fair value";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <OgShell>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 22,
            maxWidth: 900,
          }}
        >
          <div
            style={{
              fontSize: 72,
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              fontWeight: 650,
              color: "#f7f1e8",
            }}
          >
            Should you buy — or pass?
          </div>
          <div
            style={{
              fontSize: 30,
              lineHeight: 1.35,
              color: "#c9bfb3",
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
              maxWidth: 820,
            }}
          >
            Pokémon TCG spot vs a sure AI fair band. Clear calls for buy, sell,
            trade, and grade.
          </div>
          <div
            style={{
              marginTop: 8,
              display: "flex",
              gap: 12,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
              fontSize: 22,
              color: "#e0b483",
            }}
          >
            <div
              style={{
                padding: "10px 18px",
                border: "1px solid rgba(192,122,58,0.45)",
                borderRadius: 10,
                background: "rgba(192,122,58,0.16)",
              }}
            >
              Deal of the Day
            </div>
            <div
              style={{
                padding: "10px 18px",
                border: "1px solid rgba(46,41,36,0.95)",
                borderRadius: 10,
                color: "#9a9288",
              }}
            >
              Radar · Trade · Board
            </div>
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
