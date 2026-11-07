import type { Metadata } from "next";
import { Suspense } from "react";

import { LocalizedDeskLoading } from "@/components/LocalizedDeskLoading";
import { SignInPageClient } from "@/components/SignInPageClient";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign in — Kestrel",
  description: "Sign in to your Kestrel portfolio, watchlist, and Pro desks.",
  alternates: { canonical: absoluteUrl("/signin") },
  robots: { index: false, follow: true },
};

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <LocalizedDeskLoading labelKey="auth_sign_in" variant="banner" />
      }
    >
      <SignInPageClient />
    </Suspense>
  );
}
