import { MarketingLanding } from "@/components/MarketingLanding";
import { fetchCatalog } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let heroImageUrl: string | null = null;
  let heroCardName: string | null = null;

  try {
    const data = await fetchCatalog({
      mode: "browse",
      limit: 12,
      offset: 0,
      sort: "price_desc",
    });
    const withArt = data.items.find((card) => Boolean(card.image_url));
    if (withArt?.image_url) {
      heroImageUrl = withArt.image_url;
      heroCardName = withArt.name;
    }
  } catch {
    // Landing still renders with brand mark fallback.
  }

  return (
    <MarketingLanding
      heroImageUrl={heroImageUrl}
      heroCardName={heroCardName}
    />
  );
}
