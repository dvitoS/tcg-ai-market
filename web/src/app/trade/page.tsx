import { Suspense } from "react";

import { TradeView } from "@/components/TradeView";

export const dynamic = "force-dynamic";

export default function TradePage() {
  return (
    <Suspense
      fallback={
        <section className="scanner-page trade-page">
          <p className="explore-lede">Loading Trade Analyzer…</p>
        </section>
      }
    >
      <TradeView />
    </Suspense>
  );
}
