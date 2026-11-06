import { Suspense } from "react";

import { DeskLoading } from "@/components/DeskLoading";
import { PortfolioView } from "@/components/PortfolioView";

export const dynamic = "force-dynamic";

export default function PortfolioPage() {
  return (
    <Suspense
      fallback={
        <section className="portfolio-page">
          <DeskLoading label="Loading portfolio…" variant="panel" skeletonCount={4} />
        </section>
      }
    >
      <PortfolioView />
    </Suspense>
  );
}
