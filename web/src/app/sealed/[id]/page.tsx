import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SealedDetailView } from "@/components/SealedDetailView";
import { fetchSealedDetail } from "@/lib/api";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const detail = await fetchSealedDetail(id);
    const name = detail.product.name;
    const setName = detail.set_name || detail.product.set_name || "";
    return {
      title: `${name} — sealed vs singles`,
      description: setName
        ? `${name} market price with ${setName} chase singles from the Soft Ink sealed desk.`
        : `${name} market price on the Soft Ink sealed desk.`,
      alternates: { canonical: absoluteUrl(`/sealed/${encodeURIComponent(id)}`) },
    };
  } catch {
    return {
      title: "Sealed product not found",
      robots: { index: false, follow: false },
    };
  }
}

export default async function SealedDetailPage({ params }: PageProps) {
  const { id } = await params;
  let detail;
  try {
    detail = await fetchSealedDetail(id);
  } catch (err) {
    if (err instanceof Error && err.message === "NOT_FOUND") notFound();
    notFound();
  }
  return <SealedDetailView detail={detail} />;
}
