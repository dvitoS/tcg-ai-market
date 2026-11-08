import type { Metadata } from "next";

import type { Guide } from "@/lib/guides";
import { guidePath } from "@/lib/guides";
import type { CatalogCard, TradeShareView } from "@/lib/types";

export const SITE_URL = "https://www.kestreltcg.app";

export function absoluteUrl(path = "/"): string {
  if (!path || path === "/") return SITE_URL;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function cardPagePath(cardId: string): string {
  return `/cards/${encodeURIComponent(cardId)}`;
}

export function cardSeoTitle(card: CatalogCard): string {
  const set = (card.set_name || "").trim();
  return set
    ? `${card.name} — ${set} Pokémon TCG price`
    : `${card.name} — Pokémon TCG price`;
}

export function cardSeoDescription(card: CatalogCard): string {
  const set = (card.set_name || "").trim();
  const rarity = (card.rarity || "").trim();
  const spot =
    card.price != null && Number.isFinite(Number(card.price))
      ? `$${Number(card.price).toFixed(2)}`
      : null;
  const fair =
    card.predicted_price != null && Number.isFinite(Number(card.predicted_price))
      ? `$${Number(card.predicted_price).toFixed(2)}`
      : null;
  const bits = [
    set || null,
    rarity || null,
    spot ? `spot ${spot}` : null,
    fair ? `Kestrel fair ${fair}` : null,
  ].filter(Boolean);
  const lead = bits.length
    ? bits.join(" · ")
    : "Live Pokémon TCG pricing on Kestrel";
  return `${card.name}: ${lead}. Sure AI fair band, history, and buy/pass call on Kestrel.`;
}

export function cardMetadata(card: CatalogCard): Metadata {
  const title = cardSeoTitle(card);
  const description = cardSeoDescription(card);
  const url = absoluteUrl(cardPagePath(card.id));
  // Explicit absolute OG URL — Reddit / Discord unfurl reliably.
  // Image itself is rendered by app/cards/[id]/opengraph-image.tsx (1200×630).
  const ogImage = absoluteUrl(`${cardPagePath(card.id)}/opengraph-image`);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      url,
      siteName: "Kestrel",
      title,
      description,
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export function cardJsonLd(card: CatalogCard): Record<string, unknown> {
  const url = absoluteUrl(cardPagePath(card.id));
  const image = card.image_url || absoluteUrl("/kestrel-logo.png");
  const price =
    card.price != null && Number.isFinite(Number(card.price))
      ? Number(card.price).toFixed(2)
      : undefined;
  const offer = price
    ? {
        "@type": "Offer",
        url,
        priceCurrency: "USD",
        price,
        availability: "https://schema.org/InStock",
      }
    : undefined;

  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: card.name,
    sku: card.id,
    url,
    image,
    description: cardSeoDescription(card),
    category: "Pokémon TCG",
    brand: {
      "@type": "Brand",
      name: "Pokémon",
    },
    ...(card.set_name
      ? {
          isRelatedTo: {
            "@type": "ProductModel",
            name: card.set_name,
          },
        }
      : {}),
    ...(offer ? { offers: offer } : {}),
  };
}

export function tradeSharePath(shareId: string): string {
  return `/trade/s/${encodeURIComponent(shareId)}`;
}

function tradeVerdictLabel(verdict: string): string {
  const key = (verdict || "").toUpperCase();
  if (key === "YOU_AHEAD") return "You ahead";
  if (key === "THEM_AHEAD") return "Them ahead";
  return "Fair trade";
}

export function tradeShareSeoTitle(share: Pick<TradeShareView, "verdict">): string {
  return `${tradeVerdictLabel(share.verdict)} — Kestrel Trade`;
}

export function tradeShareSeoDescription(
  share: Pick<
    TradeShareView,
    "verdict" | "net_spot_pct" | "net_fair_pct" | "fair_band_pct"
  >,
): string {
  const verdict = tradeVerdictLabel(share.verdict);
  const spot =
    share.net_spot_pct != null && Number.isFinite(Number(share.net_spot_pct))
      ? `${Number(share.net_spot_pct) >= 0 ? "+" : ""}${Number(share.net_spot_pct).toFixed(1)}% spot`
      : null;
  const fair =
    share.net_fair_pct != null && Number.isFinite(Number(share.net_fair_pct))
      ? `${Number(share.net_fair_pct) >= 0 ? "+" : ""}${Number(share.net_fair_pct).toFixed(1)}% sure fair`
      : null;
  const bits = [verdict, spot, fair].filter(Boolean).join(" · ");
  return `${bits}. Desk call vs ±${share.fair_band_pct}% fair band — not financial advice.`;
}

export function tradeShareMetadata(share: TradeShareView): Metadata {
  const title = tradeShareSeoTitle(share);
  const description = tradeShareSeoDescription(share);
  const url = absoluteUrl(tradeSharePath(share.share_id));
  const ogImage = absoluteUrl(`${tradeSharePath(share.share_id)}/opengraph-image`);
  return {
    title,
    description,
    alternates: { canonical: url },
    // Share links are public previews — indexable enough for unfurl, no sitemap push.
    robots: { index: false, follow: true },
    openGraph: {
      type: "website",
      url,
      siteName: "Kestrel",
      title,
      description,
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export function guideMetadata(guide: Guide): Metadata {
  const url = absoluteUrl(guidePath(guide.slug));
  return {
    title: guide.title,
    description: guide.description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      url,
      siteName: "Kestrel",
      title: guide.title,
      description: guide.description,
    },
    twitter: {
      card: "summary_large_image",
      title: guide.title,
      description: guide.description,
    },
  };
}

export function guideJsonLd(guide: Guide): Record<string, unknown> {
  const url = absoluteUrl(guidePath(guide.slug));
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        headline: guide.title,
        description: guide.description,
        url,
        mainEntityOfPage: url,
        author: {
          "@type": "Organization",
          name: "Kestrel",
          url: SITE_URL,
        },
        publisher: {
          "@type": "Organization",
          name: "Kestrel",
          url: SITE_URL,
          logo: absoluteUrl("/kestrel-logo.png"),
        },
        inLanguage: "en",
      },
      {
        "@type": "FAQPage",
        mainEntity: guide.faqs.map((faq) => ({
          "@type": "Question",
          name: faq.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: faq.answer,
          },
        })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: "Home",
            item: SITE_URL,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: "Guides",
            item: absoluteUrl("/guides"),
          },
          {
            "@type": "ListItem",
            position: 3,
            name: guide.title,
            item: url,
          },
        ],
      },
    ],
  };
}
