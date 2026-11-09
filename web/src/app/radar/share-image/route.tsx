import { ImageResponse } from "next/og";

import { OG_SIZE, OgShell } from "@/lib/og";
import {
  decodeRadarShare,
  formatRadarShareFilters,
} from "@/lib/radarShare";

export const runtime = "edge";

export async function GET(request: Request) {
  const token = new URL(request.url).searchParams.get("share");
  const filters = decodeRadarShare(token);
  const chips = filters ? formatRadarShareFilters(filters) : [];
  const lens =
    chips.length > 0
      ? chips.slice(0, 4).join(" · ")
      : "Open filters — sure UNDER / OVER desk";

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
            Shared Radar lens
          </div>
          <div
            style={{
              fontSize: 52,
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              fontWeight: 650,
              color: "#f7f1e8",
            }}
          >
            {lens}
          </div>
          <div
            style={{
              display: "flex",
              gap: 20,
              marginTop: 4,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div
              style={{
                fontSize: 26,
                color: "#7dcea0",
                fontWeight: 650,
              }}
            >
              UNDER
            </div>
            <div style={{ fontSize: 26, color: "#9a9288" }}>·</div>
            <div
              style={{
                fontSize: 26,
                color: "#e08a7a",
                fontWeight: 650,
              }}
            >
              OVER
            </div>
            <div style={{ fontSize: 26, color: "#9a9288" }}>
              vs sure fair band
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
            Desk call, not financial advice · open live board with Pro
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
