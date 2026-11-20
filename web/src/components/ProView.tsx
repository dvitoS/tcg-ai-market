"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { DealOfTheDay } from "@/components/DealOfTheDay";
import { useLocale } from "@/components/LocaleProvider";
import { fetchBillingMe, type BillingMe } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";
import type { RadarPreviewResponse } from "@/lib/types";

export function ProView({
  checkoutUrl,
  proOpen,
  error,
  initialDotd = null,
}: {
  checkoutUrl: string | null;
  proOpen: boolean;
  error?: string | null;
  initialDotd?: RadarPreviewResponse | null;
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

  useEffect(() => {
    trackFunnel("pro_view", undefined, { once: true });
  }, []);

  const openBeta = Boolean(me?.pro_open ?? proOpen);
  const reason = me?.reason || (openBeta ? "open_beta" : "locked");
  const paidPro =
    Boolean(me?.is_pro) &&
    (reason === "entitlement" || reason === "allowlist" || reason === "pro");
  const gated = !openBeta && !paidPro;
  const effectiveCheckout = me?.checkout_url || checkoutUrl;
  const portalUrl = me?.portal_url || null;

  const title = paidPro
    ? t("pro_title_active")
    : openBeta
      ? t("pro_title_open")
      : t("pro_title");
  const lede = paidPro
    ? t("pro_lede_active")
    : openBeta
      ? t("pro_lede_open")
      : t("pro_lede");

  return (
    <main className="pro-page">
      <p className="explore-command-eyebrow">{t("pro_eyebrow")}</p>
      <h1 className="explore-title">{title}</h1>
      <p className="explore-lede">{lede}</p>

      {error ? <p className="banner-error">{error}</p> : null}
      {meError ? <p className="banner-error">{meError}</p> : null}

      {paidPro ? (
        <p className="pro-open-note pro-active-note">
          {t("pro_active_note", {
            email: me?.email || user?.email || "—",
          })}
        </p>
      ) : openBeta ? (
        <p className="pro-open-note">{t("pro_open_note")}</p>
      ) : (
        <p className="pro-open-note">{t("pro_gated_note")}</p>
      )}

      <div className="detail-actions">
        {paidPro || openBeta ? (
          <>
            <Link
              href="/radar"
              className="btn-primary"
              onClick={() =>
                trackFunnel("pro_open_radar", {
                  is_pro: paidPro,
                  open_beta: openBeta,
                })
              }
            >
              {t("pro_open_radar")}
            </Link>
            <Link
              href="/portfolio#watchlist"
              className="btn-ghost"
              onClick={() =>
                trackFunnel("pro_open_alerts", {
                  is_pro: paidPro,
                  open_beta: openBeta,
                })
              }
            >
              {t("pro_open_alerts")}
            </Link>
            {paidPro && portalUrl ? (
              <a href={portalUrl} className="btn-ghost" rel="noreferrer">
                {t("pro_manage")}
              </a>
            ) : null}
            {openBeta && !paidPro && effectiveCheckout ? (
              <a
                href={effectiveCheckout}
                className="btn-ghost"
                rel="noreferrer"
                onClick={() =>
                  trackFunnel("pro_checkout_click", { source: "pro" })
                }
              >
                {t("pro_checkout_later")}
              </a>
            ) : null}
          </>
        ) : (
          <>
            {effectiveCheckout ? (
              <a
                href={effectiveCheckout}
                className="btn-primary"
                rel="noreferrer"
                onClick={() =>
                  trackFunnel("pro_checkout_click", { source: "pro" })
                }
              >
                {t("dealer_upgrade")}
              </a>
            ) : (
              <span className="btn-ghost is-disabled" aria-disabled="true">
                {t("pro_checkout_missing")}
              </span>
            )}
            <Link
              href="/radar"
              className="btn-ghost"
              onClick={() => trackFunnel("pro_open_radar", { is_pro: false })}
            >
              {t("pro_open_radar")}
            </Link>
            {!user ? (
              <Link href="/signin?next=/pro" className="btn-ghost">
                {t("auth_sign_in")}
              </Link>
            ) : null}
          </>
        )}
      </div>

      <DealOfTheDay
        limit={5}
        variant="pro"
        initialPreview={initialDotd}
        openBeta={openBeta}
      />

      <section className="pro-alerts-teaser" aria-labelledby="pro-alerts-title">
        <h2 id="pro-alerts-title" className="pro-guides-title">
          {t("pro_alerts_title")}
        </h2>
        <p className="explore-lede">{t("pro_alerts_lede")}</p>
        <Link
          href="/portfolio#watchlist"
          className="btn-ghost"
          onClick={() =>
            trackFunnel("pro_open_alerts", {
              is_pro: paidPro,
              open_beta: openBeta,
              source: "pro_teaser",
            })
          }
        >
          {t("pro_alerts_cta")}
        </Link>
      </section>

      <ul className="pro-feature-list">
        <li>{t("pro_f1")}</li>
        <li>{t("pro_f2")}</li>
      </ul>

      <p className="lot-meta pro-more-desks">
        <Link
          href="/trade"
          onClick={() =>
            trackFunnel("pro_open_trade", {
              is_pro: paidPro,
              open_beta: openBeta,
            })
          }
        >
          {t("pro_open_trade")}
        </Link>
        {" · "}
        <Link href="/dealer">{t("pro_open_dealer")}</Link>
      </p>
    </main>
  );
}
