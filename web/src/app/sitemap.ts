import type { MetadataRoute } from "next";

import { fetchCatalog } from "@/lib/api";
import { absoluteUrl, cardPagePath } from "@/lib/seo";

const PAGE_SIZE = 500;
/** Cap crawl budget — top priced board first; expand later if Search Console wants more. */
const MAX_CARD_URLS = 2000;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticPaths: MetadataRoute.Sitemap = [
    {
      url: absoluteUrl("/"),
      lastModified: now,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: absoluteUrl("/browse"),
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: absoluteUrl("/pro"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: absoluteUrl("/radar"),
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: absoluteUrl("/trade"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: absoluteUrl("/portfolio"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.55,
    },
    {
      url: absoluteUrl("/binder"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.5,
    },
    {
      url: absoluteUrl("/scanner"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.45,
    },
    {
      url: absoluteUrl("/identify"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.45,
    },
    {
      url: absoluteUrl("/dealer"),
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.4,
    },
  ];

  const cardEntries: MetadataRoute.Sitemap = [];
  const seen = new Set<string>();

  try {
    let offset = 0;
    while (cardEntries.length < MAX_CARD_URLS) {
      const page = await fetchCatalog(
        {
          mode: "browse",
          limit: PAGE_SIZE,
          offset,
          sort: "price_desc",
        },
        { next: { revalidate: 3600 } },
      );
      const items = page.items || [];
      if (items.length === 0) break;

      for (const card of items) {
        if (!card?.id || seen.has(card.id)) continue;
        seen.add(card.id);
        cardEntries.push({
          url: absoluteUrl(cardPagePath(card.id)),
          lastModified: now,
          changeFrequency: "daily",
          priority: 0.7,
        });
        if (cardEntries.length >= MAX_CARD_URLS) break;
      }

      offset += PAGE_SIZE;
      if (offset >= (page.total || 0) || items.length < PAGE_SIZE) break;
    }
  } catch {
    // Keep static sitemap if the API is cold / unreachable at build/request time.
  }

  return [...staticPaths, ...cardEntries];
}
