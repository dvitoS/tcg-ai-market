import type { Metadata } from "next";

import { SealedDesk } from "@/components/SealedDesk";
import { fetchSealedQuote } from "@/lib/api";
import { absoluteUrl } from "@/lib/seo";
import type { SealedQuoteResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sealed Pokémon TCG products — ETB, boxes, tins",
  description:
    "Compare sealed Pokémon prices (ETBs, booster boxes, tins) to set singles, then add products to your portfolio.",
  alternates: { canonical: absoluteUrl("/sealed") },
};

export default async function SealedPage() {
  let initial: SealedQuoteResponse | null = null;
  try {
    initial = await fetchSealedQuote({ limit: 48 });
  } catch {
    initial = null;
  }
  return <SealedDesk initial={initial} />;
}
