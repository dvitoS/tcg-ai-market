import { ImageResponse } from "next/og";

import { cleanBinderShareSet } from "@/lib/binderExport";
import { OG_SIZE, OgShell } from "@/lib/og";

export const runtime = "edge";

export async function GET(request: Request) {
  const raw = new URL(request.url).searchParams.get("set");
  const setName = cleanBinderShareSet(raw);
  const headline = setName || "Pokémon TCG set";

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
            Shared binder set
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
            {headline}
          </div>
          <div
            style={{
              display: "flex",
              gap: 20,
              marginTop: 4,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
              fontSize: 26,
              color: "#e0b483",
              fontWeight: 650,
            }}
          >
            Owned · Missing · Buy-cost to finish
          </div>
          <div
            style={{
              marginTop: 10,
              fontSize: 22,
              color: "#9a9288",
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            No private P&amp;L · open live checklist on Kestrel
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
