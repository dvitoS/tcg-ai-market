import type { Metadata } from "next";

import { MarketingLanding } from "@/components/MarketingLanding";
import { fetchMarketPulse, fetchRadarPreview } from "@/lib/api";
import { SITE_URL, absoluteUrl } from "@/lib/seo";

const TITLE = "Kestrel — Pokémon card prices: buy, skip, or trade";
const DESCRIPTION =
  "Most apps show one market price. Kestrel shows market price next to a AI fair so you can buy, skip, trade, or grade with a clearer read.";

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
    "AI fair",
    "market price",
    "TCG market",
    "Kestrel",
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
      inLanguage: ["en"],
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
      name: "Kestrel",
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

async function withBudget<T>(
  promise: Promise<T>,
  ms: number,
): Promise<T | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), ms);
      }),
    ]);
  } catch {
    return null;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export default async function HomePage() {
  // Cap SSR wait — cold API must not hold Soft Nav / LCP hostage (~4s+).
  const [dotd, pulse] = await Promise.all([
    withBudget(fetchRadarPreview(5), 700),
    withBudget(fetchMarketPulse(5), 700),
  ]);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <MarketingLanding
        initialDotd={dotd}
        initialPulse={pulse}
      />
    </>
  );
}
