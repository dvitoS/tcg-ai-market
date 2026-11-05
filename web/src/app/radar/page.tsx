import { Suspense } from "react";

import { RadarView } from "@/components/RadarView";

export const dynamic = "force-dynamic";

export default function RadarPage() {
  return (
    <Suspense fallback={<p className="explore-lede">Loading Kestrel Radar…</p>}>
      <RadarView />
    </Suspense>
  );
}
