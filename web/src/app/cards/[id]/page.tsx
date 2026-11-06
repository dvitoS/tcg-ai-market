import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CardDetailView } from "@/components/CardDetailView";
import { fetchCardDetail } from "@/lib/api";
import { cardJsonLd, cardMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const detail = await fetchCardDetail(id);
    return cardMetadata(detail.card);
  } catch {
    return {
      title: "Card not found",
      robots: { index: false, follow: false },
    };
  }
}

export default async function CardDetailPage({ params }: PageProps) {
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
  const jsonLd = cardJsonLd(detail.card);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <CardDetailView detail={detail} points={points} />
    </>
  );
}
