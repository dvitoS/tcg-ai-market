import type { Metadata } from "next";

import { SealedDesk } from "@/components/SealedDesk";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sealed Pokémon TCG products — ETB, boxes, tins",
  description:
    "Quote sealed Pokémon TCG products (ETB, booster boxes, tins) via JustTCG and add them to your Kestrel portfolio.",
  alternates: { canonical: absoluteUrl("/sealed") },
};

export default function SealedPage() {
  return <SealedDesk />;
}
