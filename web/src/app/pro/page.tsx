import type { Metadata } from "next";

import { ProView } from "@/components/ProView";
import { fetchBillingStatus, fetchRadarPreview } from "@/lib/api";
import { absoluteUrl } from "@/lib/seo";
import type { RadarPreviewResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Kestrel Pro — Radar, Trade Analyzer, dealer desk",
  description:
    "Unlock Kestrel Radar, Trade Analyzer, dealer scoring, and sure-only alerts. €7/mo after a 7-day trial.",
  alternates: { canonical: absoluteUrl("/pro") },
};

export default async function ProPage() {
  let checkoutUrl: string | null = null;
  let proOpen = true;
  let error: string | null = null;
  let initialDotd: RadarPreviewResponse | null = null;
  try {
    const [status, preview] = await Promise.all([
      fetchBillingStatus(),
      fetchRadarPreview(5).catch(() => null),
    ]);
    checkoutUrl = status.checkout_url;
    proOpen = status.pro_open;
    initialDotd = preview;
  } catch (err) {
    error = err instanceof Error ? err.message : "Could not load billing status";
  }

  return (
    <ProView
      checkoutUrl={checkoutUrl}
      proOpen={proOpen}
      error={error}
      initialDotd={initialDotd}
    />
  );
}
