import { Suspense } from "react";

import { AuthCallbackView } from "@/components/AuthCallbackView";
import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <LocalizedDeskLoading labelKey="auth_google_finishing" variant="panel" />
      }
    >
      <AuthCallbackView />
    </Suspense>
  );
}
