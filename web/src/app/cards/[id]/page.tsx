import { notFound } from "next/navigation";

import { CardDetailView } from "@/components/CardDetailView";
import { fetchCardDetail } from "@/lib/api";

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

  // Prefer points embedded on detail (one round-trip); fall back to empty.
  const points = detail.points ?? [];

  return <CardDetailView detail={detail} points={points} />;
}
