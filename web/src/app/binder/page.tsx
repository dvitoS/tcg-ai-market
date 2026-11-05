import { Suspense } from "react";

import { BinderView } from "@/components/BinderView";

export const dynamic = "force-dynamic";

export default function BinderPage() {
  return (
    <Suspense fallback={<p className="explore-lede">Loading binder…</p>}>
      <BinderView />
    </Suspense>
  );
}
