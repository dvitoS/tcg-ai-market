import type { Metadata } from "next";

import { TradeShareView } from "@/components/TradeShareView";
import { apiUrl } from "@/lib/api";
import { tradeShareMetadata } from "@/lib/seo";
import type { TradeShareView as TradeSharePayload } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

async function loadShare(shareId: string): Promise<TradeSharePayload | null> {
  const id = encodeURIComponent(shareId).replace(/%2F/gi, "/");
  try {
    const res = await fetch(apiUrl(`/api/trade/share/${id}`), {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as TradeSharePayload;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const shareId = decodeURIComponent(id || "").trim();
  if (!shareId) {
    return {
      title: "Trade share",
      robots: { index: false, follow: false },
    };
  }
  const share = await loadShare(shareId);
  if (!share) {
    return {
      title: "Trade share not found",
      robots: { index: false, follow: false },
    };
  }
  return tradeShareMetadata(share);
}

export default async function TradeSharePage({ params }: Props) {
  const { id } = await params;
  const shareId = decodeURIComponent(id || "").trim();
  return <TradeShareView shareId={shareId} />;
}
