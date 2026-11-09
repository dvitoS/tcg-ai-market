import type { Metadata } from "next";
import { Suspense } from "react";

import { BinderView } from "@/components/BinderView";
import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { cleanBinderShareSet } from "@/lib/binderExport";
import { absoluteUrl, binderShareMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<{ set?: string | string[] }>;
};

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const params = await searchParams;
  const raw = params.set;
  const setName = cleanBinderShareSet(Array.isArray(raw) ? raw[0] : raw);
  if (setName) {
    return binderShareMetadata(setName);
  }
  return {
    title: "Kestrel binder — set completion",
    description:
      "Track Pokémon TCG set completion on Kestrel — owned, missing, and buy-cost to finish. No private P&L on shared links.",
    alternates: { canonical: absoluteUrl("/binder") },
    openGraph: {
      type: "website",
      url: absoluteUrl("/binder"),
      siteName: "Kestrel",
      title: "Kestrel binder — set completion",
      description:
        "Owned / missing / buy-cost checklist — desk tool, not a social binder feed.",
      images: [
        {
          url: absoluteUrl("/binder/opengraph-image"),
          width: 1200,
          height: 630,
          alt: "Kestrel binder",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Kestrel binder — set completion",
      description: "Owned / missing / buy-cost checklist on Kestrel.",
      images: [absoluteUrl("/binder/opengraph-image")],
    },
  };
}

export default function BinderPage() {
  return (
    <Suspense
      fallback={
        <LocalizedDeskLoading labelKey="binder_loading" variant="banner" />
      }
    >
      <BinderView />
    </Suspense>
  );
}
