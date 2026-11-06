import type { Metadata } from "next";

import { MarketingLanding } from "@/components/MarketingLanding";

const SITE = "https://www.kestreltcg.app";
const TITLE = "Kestrel — Pokémon TCG fair value: buy, pass, or trade";
const DESCRIPTION =
  "Kestrel Soft Ink scores Pokémon TCG spot against a sure AI fair band. Deal of the Day, Radar, Trade Analyzer, and live board prices — clear calls, not vibes.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: {
    canonical: SITE,
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
    url: SITE,
    siteName: "Kestrel",
    title: TITLE,
    description: DESCRIPTION,
    locale: "en_US",
    images: [
      {
        url: `${SITE}/kestrel-logo.png`,
        width: 512,
        height: 512,
        alt: "Kestrel Soft Ink",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: TITLE,
    description: DESCRIPTION,
    images: [`${SITE}/kestrel-logo.png`],
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
      "@id": `${SITE}/#website`,
      url: SITE,
      name: "Kestrel",
      description: DESCRIPTION,
      publisher: { "@id": `${SITE}/#organization` },
      inLanguage: ["en", "hr"],
    },
    {
      "@type": "Organization",
      "@id": `${SITE}/#organization`,
      name: "Kestrel",
      url: SITE,
      logo: `${SITE}/kestrel-logo.png`,
    },
    {
      "@type": "SoftwareApplication",
      name: "Kestrel Soft Ink",
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      url: SITE,
      description: DESCRIPTION,
      offers: {
        "@type": "Offer",
        price: "7.00",
        priceCurrency: "EUR",
        category: "Subscription",
        url: `${SITE}/pro`,
      },
    },
  ],
};

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <MarketingLanding />
    </>
  );
}
