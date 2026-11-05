import { TradeShareView } from "@/components/TradeShareView";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function TradeSharePage({ params }: Props) {
  const { id } = await params;
  const shareId = decodeURIComponent(id || "").trim();
  return <TradeShareView shareId={shareId} />;
}
