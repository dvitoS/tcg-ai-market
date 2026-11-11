import { cache } from "react";

import { fetchCardDetail } from "@/lib/api";
import type { CardDetailResponse } from "@/lib/types";

/** Deduplicate Soft Ink SSR: generateMetadata + page share one API round-trip. */
export const loadCardDetail = cache(
  async (cardId: string): Promise<CardDetailResponse> => fetchCardDetail(cardId),
);
