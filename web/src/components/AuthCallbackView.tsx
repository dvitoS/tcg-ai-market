"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { setAccessToken } from "@/lib/api";
import { getSupabaseBrowser } from "@/lib/supabaseBrowser";

function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/portfolio";
  return raw;
}

export function AuthCallbackView() {
  const { t } = useLocale();
  const router = useRouter();
  const search = useSearchParams();
  const { refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    let cancelled = false;

    async function finish() {
      const next = safeNext(search.get("next"));
      const client = getSupabaseBrowser();
      if (!client) {
        if (!cancelled) setError(t("auth_google_unavailable"));
        return;
      }

      try {
        const code = search.get("code");
        let token: string | undefined;

        if (code) {
          const { data, error: exchangeError } =
            await client.auth.exchangeCodeForSession(code);
          if (exchangeError) {
            // Effect remount / prior exchange may have already created a session.
            const { data: existing, error: sessionError } =
              await client.auth.getSession();
            if (sessionError) throw exchangeError;
            token = existing.session?.access_token;
            if (!token) throw exchangeError;
          } else {
            token = data.session?.access_token;
          }
        } else {
          // Implicit / hash recovery fallback (older Supabase redirects).
          const { data, error: sessionError } = await client.auth.getSession();
          if (sessionError) throw sessionError;
          token = data.session?.access_token;
        }

        if (!token) throw new Error(t("auth_google_failed"));
        setAccessToken(token);
        await refresh();
        if (!cancelled) router.replace(next);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : t("auth_google_failed"),
          );
        }
      }
    }

    void finish();
    return () => {
      cancelled = true;
    };
  }, [refresh, router, search, t]);

  if (error) {
    return (
      <section className="scanner-page auth-callback-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("auth_sign_in")}</p>
          <h1 className="explore-title">{t("auth_google_failed")}</h1>
          <p className="explore-lede">{error}</p>
        </div>
        <div className="detail-actions">
          <Link href="/signin" className="btn-primary">
            {t("auth_sign_in")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="scanner-page auth-callback-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("auth_sign_in")}</p>
        <h1 className="explore-title">{t("auth_google_finishing")}</h1>
      </div>
      <DeskLoading
        label={t("auth_google_finishing")}
        variant="panel"
        skeletonCount={3}
      />
    </section>
  );
}
