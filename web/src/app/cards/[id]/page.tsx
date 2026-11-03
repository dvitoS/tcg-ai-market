import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { apiUrl, formatChange, formatMoney } from "@/lib/api";
import type { CatalogCard } from "@/lib/types";

export const dynamic = "force-dynamic";

type DetailPayload = {
  card: CatalogCard;
  pred_lo_pct?: number | null;
  pred_hi_pct?: number | null;
};

async function loadCard(id: string): Promise<DetailPayload | null> {
  try {
    const res = await fetch(apiUrl(`/api/cards/${encodeURIComponent(id)}`), {
      headers: { Accept: "application/json" },
      next: { revalidate: 30 },
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Detail failed (${res.status})`);
    return (await res.json()) as DetailPayload;
  } catch {
    return null;
  }
}

export default async function CardDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await loadCard(id);
  if (!data) notFound();

  const { card } = data;
  const meta = [card.set_name, card.rarity].filter(Boolean).join(" · ");
  const image = card.image_url || "/kestrel-logo.png";

  return (
    <article className="detail-page">
      <Link href="/" className="detail-back">
        ← Back to browse
      </Link>
      <div className="detail-hero">
        <div className="detail-art">
          <Image src={image} alt={card.name} width={420} height={586} priority />
        </div>
        <div>
          <p className="detail-kicker">Card detail</p>
          <h1 className="detail-name">{card.name}</h1>
          <p className="detail-meta">{meta}</p>
          <div className="detail-price">{formatMoney(card.price)}</div>
          <div className="detail-ai">
            <div>
              <span>AI ROI</span>
              <strong>{formatChange(card.expected_change_pct)}</strong>
            </div>
            <div>
              <span>Signal</span>
              <strong>{card.signal || "—"}</strong>
            </div>
            <div>
              <span>Predicted</span>
              <strong>{formatMoney(card.predicted_price)}</strong>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
