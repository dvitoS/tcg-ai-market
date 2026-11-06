import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { GuideArticle } from "@/components/GuideArticle";
import { GUIDES, getGuide } from "@/lib/guides";
import { guideMetadata } from "@/lib/seo";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return GUIDES.map((guide) => ({ slug: guide.slug }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const guide = getGuide(slug);
  if (!guide) {
    return { title: "Guide not found", robots: { index: false, follow: false } };
  }
  return guideMetadata(guide);
}

export default async function GuidePage({ params }: PageProps) {
  const { slug } = await params;
  const guide = getGuide(slug);
  if (!guide) notFound();
  return <GuideArticle guide={guide} />;
}
