import type { Metadata } from "next";

import type { Guide } from "@/lib/guides";
import { guidePath } from "@/lib/guides";
import type { CatalogCard } from "@/lib/types";

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
  // Share preview image comes from app/cards/[id]/opengraph-image.tsx (1200×630).
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
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
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
