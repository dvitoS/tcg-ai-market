import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CardDetailView } from "@/components/CardDetailView";
import { resolveCardImageUrl } from "@/lib/cardImage";
import { loadCardDetail } from "@/lib/cardDetail";
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
    const detail = await loadCardDetail(id);
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
    detail = await loadCardDetail(id);
  } catch (err) {
    if (err instanceof Error && err.message === "NOT_FOUND") notFound();
    notFound();
  }

  // Prefer points embedded on detail (one round-trip); fall back to empty.
  const points = detail.points ?? [];
  const jsonLd = cardJsonLd(detail.card);
  // Must match CardDetailView → HoloCardArt `src` or Chrome warns
  // "preloaded … but not used" (low.webp was never rendered on detail).
  const lcpImage = resolveCardImageUrl(detail.card.id, detail.card.image_url);

  return (
    <>
      {lcpImage.startsWith("http") ? (
        <link
          rel="preload"
          as="image"
          href={lcpImage}
          fetchPriority="high"
        />
      ) : null}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <CardDetailView detail={detail} points={points} />
    </>
  );
}
