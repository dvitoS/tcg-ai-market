import type { Metadata } from "next";
import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { RadarView } from "@/components/RadarView";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Kestrel Radar — sure underpriced Pokémon cards",
  description:
    "Kestrel Radar lists Pokémon TCG singles selling under or over the sure AI fair band — clear buy/pass calls.",
  alternates: { canonical: absoluteUrl("/radar") },
};

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
