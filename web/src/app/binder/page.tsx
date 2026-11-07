import { Suspense } from "react";

import { BinderView } from "@/components/BinderView";
import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";

export const dynamic = "force-dynamic";

export default function BinderPage() {
  return (
    <Suspense
      fallback={
        <LocalizedDeskLoading labelKey="binder_loading" variant="banner" />
      }
    >
      <BinderView />
    </Suspense>
  );
}
