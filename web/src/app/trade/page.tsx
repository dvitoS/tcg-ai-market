import type { Metadata } from "next";
import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { TradeView } from "@/components/TradeView";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Trade check — fair Pokémon card trades",
  description:
    "Score two-sided Pokémon trades on market price and AI fair. Fair, you’re ahead, or they’re ahead in seconds.",
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
