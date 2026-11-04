"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchBillingMe, type BillingMe } from "@/lib/api";

export function ProView({
  checkoutUrl,
  proOpen,
  error,
}: {
  checkoutUrl: string | null;
  proOpen: boolean;
  error?: string | null;
}) {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const [me, setMe] = useState<BillingMe | null>(null);
  const [meError, setMeError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    setMeError(null);
    try {
      setMe(await fetchBillingMe());
    } catch (err) {
      setMe(null);
      setMeError(err instanceof Error ? err.message : t("pro_status_error"));
    }
  }, [t]);

  useEffect(() => {
    if (authLoading) return;
    void loadMe();
  }, [authLoading, user, loadMe]);

  const isPro = Boolean(me?.is_pro);
  const effectiveCheckout = me?.checkout_url || checkoutUrl;
  const portalUrl = me?.portal_url || null;
  const gated = !(me?.pro_open ?? proOpen);

  return (
    <main className="pro-page">
      <p className="explore-command-eyebrow">{t("pro_eyebrow")}</p>
      <h1 className="explore-title">
        {isPro ? t("pro_title_active") : t("pro_title")}
      </h1>
      <p className="explore-lede">
        {isPro ? t("pro_lede_active") : t("pro_lede")}
      </p>

      {error ? <p className="banner-error">{error}</p> : null}
      {meError ? <p className="banner-error">{meError}</p> : null}

      {isPro ? (
        <p className="pro-open-note pro-active-note">
          {t("pro_active_note", {
            email: me?.email || user?.email || "—",
          })}
        </p>
      ) : !gated ? (
        <p className="pro-open-note">{t("pro_open_note")}</p>
      ) : (
        <p className="pro-open-note">{t("pro_gated_note")}</p>
      )}

      <div className="detail-actions">
        {isPro ? (
          <>
            <Link href="/radar" className="btn-primary">
              {t("pro_open_radar")}
            </Link>
            <Link href="/dealer" className="btn-ghost">
              {t("pro_open_dealer")}
            </Link>
            {portalUrl ? (
              <a href={portalUrl} className="btn-ghost" rel="noreferrer">
                {t("pro_manage")}
              </a>
            ) : null}
          </>
        ) : (
          <>
            {effectiveCheckout ? (
              <a href={effectiveCheckout} className="btn-primary" rel="noreferrer">
                {t("dealer_upgrade")}
              </a>
            ) : (
              <span className="btn-ghost is-disabled" aria-disabled="true">
                {t("pro_checkout_missing")}
              </span>
            )}
            <Link href="/radar" className="btn-ghost">
              {t("pro_open_radar")}
            </Link>
            <Link href="/dealer" className="btn-ghost">
              {t("pro_open_dealer")}
            </Link>
            {!user ? (
              <Link href="/portfolio" className="btn-ghost">
                {t("auth_sign_in")}
              </Link>
            ) : null}
          </>
        )}
      </div>

      <ul className="pro-feature-list">
        <li>{t("pro_f1")}</li>
        <li>{t("pro_f2")}</li>
        <li>{t("pro_f3")}</li>
      </ul>
    </main>
  );
}
