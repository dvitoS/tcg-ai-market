import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CardDetailView } from "@/components/CardDetailView";
import { resolveCardImageUrl, tcgdexImageUrlLow } from "@/lib/cardImage";
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
  const lcpImage = resolveCardImageUrl(detail.card.id, detail.card.image_url);
  const lcpLow = tcgdexImageUrlLow(detail.card.id);
  const preloadHref =
    lcpLow && lcpLow.startsWith("http") ? lcpLow : lcpImage;

  return (
    <>
      {preloadHref.startsWith("http") ? (
        <link
          rel="preload"
          as="image"
          href={preloadHref}
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
