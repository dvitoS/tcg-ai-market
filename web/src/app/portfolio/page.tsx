import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { PortfolioView } from "@/components/PortfolioView";

export const dynamic = "force-dynamic";

export default function PortfolioPage() {
  return (
    <Suspense
      fallback={
        <section className="portfolio-page">
          <LocalizedDeskLoading
            labelKey="port_loading_desk"
            variant="panel"
            skeletonCount={4}
          />
        </section>
      }
    >
      <PortfolioView />
    </Suspense>
  );
}
