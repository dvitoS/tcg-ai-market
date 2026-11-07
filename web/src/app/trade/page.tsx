import type { Metadata } from "next";
import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { TradeView } from "@/components/TradeView";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Trade Analyzer — fair Pokémon TCG trades",
  description:
    "Score two-sided Pokémon TCG trades against spot and Kestrel AI fair value. Fair, you-ahead, or them-ahead in seconds.",
  alternates: { canonical: absoluteUrl("/trade") },
};

export default function TradePage() {
  return (
    <Suspense
      fallback={
        <section className="scanner-page trade-page">
          <LocalizedDeskLoading labelKey="trade_loading" variant="banner" />
        </section>
      }
    >
      <TradeView />
    </Suspense>
  );
}
