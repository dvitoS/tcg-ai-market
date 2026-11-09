import type { Metadata } from "next";
import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { RadarView } from "@/components/RadarView";
import { decodeRadarShare } from "@/lib/radarShare";
import { absoluteUrl, radarShareMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<{ share?: string | string[] }>;
};

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const params = await searchParams;
  const raw = params.share;
  const token = Array.isArray(raw) ? raw[0] : raw;
  const filters = decodeRadarShare(token);
  if (filters && token) {
    return radarShareMetadata(filters, token);
  }
  return {
    title: "Kestrel Radar — sure underpriced Pokémon cards",
    description:
      "Kestrel Radar lists Pokémon TCG singles selling under or over the sure AI fair band — clear buy/pass calls.",
    alternates: { canonical: absoluteUrl("/radar") },
    openGraph: {
      type: "website",
      url: absoluteUrl("/radar"),
      siteName: "Kestrel",
      title: "Kestrel Radar — sure underpriced Pokémon cards",
      description:
        "Sure UNDER/OVER vs the fair band — desk call, not financial advice. Open with Kestrel Pro.",
      images: [
        {
          url: absoluteUrl("/radar/opengraph-image"),
          width: 1200,
          height: 630,
          alt: "Kestrel Radar",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Kestrel Radar — sure underpriced Pokémon cards",
      description:
        "Sure UNDER/OVER vs the fair band — desk call, not financial advice.",
      images: [absoluteUrl("/radar/opengraph-image")],
    },
  };
}

export default function RadarPage() {
  return (
    <Suspense
      fallback={
        <LocalizedDeskLoading labelKey="radar_loading" variant="panel" />
      }
    >
      <RadarView />
    </Suspense>
  );
}
