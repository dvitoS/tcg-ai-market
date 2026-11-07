"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/AuthProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { SignInView } from "@/components/SignInView";

function safeNextPath(raw: string | null): string {
  if (!raw) return "/portfolio";
  const path = raw.trim();
  if (!path.startsWith("/") || path.startsWith("//")) return "/portfolio";
  return path;
}

export function SignInPageClient() {
  const { t } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const nextPath = safeNextPath(searchParams.get("next"));
  const authParam = (searchParams.get("auth") || "").trim().toLowerCase();
  const initialMode =
    authParam === "signup" || authParam === "forgot" ? authParam : "signin";

  useEffect(() => {
    if (!loading && user) {
      router.replace(nextPath);
    }
  }, [loading, user, nextPath, router]);

  if (loading || user) {
    return (
      <section className="portfolio-page">
        <DeskLoading label={t("port_loading")} variant="banner" />
      </section>
    );
  }

  return (
    <SignInView
      nextPath={nextPath}
      initialMode={initialMode}
      onAuthenticated={async () => {
        router.replace(nextPath);
      }}
    />
  );
}
