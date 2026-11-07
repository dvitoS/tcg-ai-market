import type { Metadata } from "next";

import { MarketingLanding } from "@/components/MarketingLanding";
import {
  fetchMarketPulse,
  fetchRadarPreview,
  fetchSealedQuote,
} from "@/lib/api";
import { SITE_URL, absoluteUrl } from "@/lib/seo";
import type {
  MarketPulseResponse,
  RadarPreviewResponse,
  SealedQuoteResponse,
} from "@/lib/types";

const TITLE = "Kestrel Soft Ink — Pokémon TCG fair value: buy, pass, or trade";
const DESCRIPTION =
  "Price trackers show the spot. Kestrel Soft Ink scores Pokémon TCG cards against a sure AI fair band — buy, sell, trade, or grade with a clear call.";

export const metadata: Metadata = {
  title: {
    absolute: TITLE,
  },
  description: DESCRIPTION,
  alternates: {
    canonical: SITE_URL,
  },
  keywords: [
    "Pokémon TCG",
    "Pokemon card prices",
    "fair value",
    "TCG market",
    "Kestrel",
    "Soft Ink",
    "trade analyzer",
    "deal of the day",
  ],
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "Kestrel",
    title: TITLE,
    description: DESCRIPTION,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "Kestrel",
      description: DESCRIPTION,
      publisher: { "@id": `${SITE_URL}/#organization` },
      inLanguage: ["en", "hr"],
    },
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: "Kestrel",
      url: SITE_URL,
      logo: absoluteUrl("/kestrel-logo.png"),
    },
    {
      "@type": "SoftwareApplication",
      name: "Kestrel Soft Ink",
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      url: SITE_URL,
      description: DESCRIPTION,
      offers: {
        "@type": "Offer",
        price: "7.00",
        priceCurrency: "EUR",
        category: "Subscription",
        url: absoluteUrl("/pro"),
      },
    },
  ],
};

export default async function HomePage() {
  let initialDotd: RadarPreviewResponse | null = null;
  let initialPulse: MarketPulseResponse | null = null;
  let initialSealed: SealedQuoteResponse | null = null;
  const [dotd, pulse, sealed] = await Promise.allSettled([
    fetchRadarPreview(5),
    fetchMarketPulse(5),
    fetchSealedQuote({ limit: 4 }),
  ]);
  if (dotd.status === "fulfilled") initialDotd = dotd.value;
  if (pulse.status === "fulfilled") initialPulse = pulse.value;
  if (sealed.status === "fulfilled") initialSealed = sealed.value;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <MarketingLanding
        initialDotd={initialDotd}
        initialPulse={initialPulse}
        initialSealed={initialSealed}
      />
    </>
  );
}
