import { ImageResponse } from "next/og";

import { apiUrl } from "@/lib/api";
import { OG_SIZE, OgShell } from "@/lib/og";
import type { CardDetailResponse } from "@/lib/types";

export const alt = "Kestrel card price";
export const size = OG_SIZE;
export const contentType = "image/png";

async function loadCard(id: string): Promise<CardDetailResponse["card"] | null> {
  try {
    const res = await fetch(apiUrl(`/api/cards/${encodeURIComponent(id)}`), {
      headers: { Accept: "application/json" },
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    const body = (await res.json()) as CardDetailResponse;
    return body.card || null;
  } catch {
    return null;
  }
}

function money(value?: number | null): string | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return `$${Number(value).toFixed(2)}`;
}

export default async function CardOpenGraphImage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const card = await loadCard(id);
  const name = card?.name || "Pokémon TCG card";
  const setName = card?.set_name || "";
  const spot = money(card?.price);
  const fair = money(card?.predicted_price);
  const imageUrl = card?.image_url || null;

  return new ImageResponse(
    (
      <OgShell footer="kestreltcg.app/cards">
        <div
          style={{
            display: "flex",
            gap: 40,
            alignItems: "center",
            width: "100%",
          }}
        >
          <div
            style={{
              width: 220,
              height: 308,
              borderRadius: 16,
              border: "1px solid #2e2924",
              background: "#171411",
              overflow: "hidden",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                width={220}
                height={308}
                alt=""
                style={{ objectFit: "cover", width: 220, height: 308 }}
              />
            ) : (
              <div
                style={{
                  fontSize: 28,
                  color: "#9a9288",
                  fontFamily: "ui-sans-serif, system-ui, sans-serif",
                }}
              >
                Kestrel
              </div>
            )}
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 16,
              flex: 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                fontSize: 54,
                lineHeight: 1.05,
                letterSpacing: "-0.03em",
                fontWeight: 650,
                color: "#f7f1e8",
              }}
            >
              {name}
            </div>
            {setName ? (
              <div
                style={{
                  fontSize: 26,
                  color: "#9a9288",
                  fontFamily: "ui-sans-serif, system-ui, sans-serif",
                }}
              >
                {setName}
                {card?.rarity ? ` · ${card.rarity}` : ""}
              </div>
            ) : null}
            <div
              style={{
                display: "flex",
                gap: 28,
                marginTop: 8,
                fontFamily: "ui-sans-serif, system-ui, sans-serif",
              }}
            >
              {spot ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ fontSize: 18, color: "#9a9288" }}>Spot</div>
                  <div style={{ fontSize: 40, color: "#f7f1e8", fontWeight: 650 }}>
                    {spot}
                  </div>
                </div>
              ) : null}
              {fair ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ fontSize: 18, color: "#9a9288" }}>Kestrel fair</div>
                  <div style={{ fontSize: 40, color: "#e0b483", fontWeight: 650 }}>
                    {fair}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </OgShell>
    ),
    { ...OG_SIZE },
  );
}
