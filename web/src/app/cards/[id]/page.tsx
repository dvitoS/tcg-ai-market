import { notFound } from "next/navigation";

import { CardDetailView } from "@/components/CardDetailView";
import { fetchCardDetail, fetchCardHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CardDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let detail;
  try {
    detail = await fetchCardDetail(id);
  } catch (err) {
    if (err instanceof Error && err.message === "NOT_FOUND") notFound();
    notFound();
  }

  let points = [] as Awaited<ReturnType<typeof fetchCardHistory>>["points"];
  try {
    const history = await fetchCardHistory(id, 180);
    points = history.points;
  } catch {
    points = [];
  }

  return <CardDetailView detail={detail} points={points} />;
}
