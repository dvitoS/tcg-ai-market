"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import {
  fetchBillingMe,
  fetchRadarPreview,
  formatChange,
  formatMoney,
  type BillingMe,
} from "@/lib/api";
import type { RadarPreviewResponse } from "@/lib/types";

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
  const [preview, setPreview] = useState<RadarPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);

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
    let alive = true;
    setPreviewLoading(true);
    void fetchRadarPreview(5)
      .then((payload) => {
        if (!alive) return;
        setPreview(payload);
        setPreviewError(null);
      })
      .catch((err) => {
        if (!alive) return;
        setPreview(null);
        setPreviewError(err instanceof Error ? err.message : t("pro_demo_error"));
      })
      .finally(() => {
        if (alive) setPreviewLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [t]);

  const isPro = Boolean(me?.is_pro);
  const effectiveCheckout = me?.checkout_url || checkoutUrl;
  const portalUrl = me?.portal_url || null;
  const gated = !(me?.pro_open ?? proOpen);
  const rows = preview?.underpriced || [];

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
            <Link href="/trade" className="btn-ghost">
              {t("pro_open_trade")}
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
            <Link href="/trade" className="btn-ghost">
              {t("pro_open_trade")}
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

      <section className="pro-demo" aria-label={t("pro_demo_title")}>
        <p className="explore-command-eyebrow">{t("pro_demo_eyebrow")}</p>
        <h2 className="pro-demo-title">{t("pro_demo_title")}</h2>
        <p className="explore-lede">
          {t("pro_demo_lede")}
          {preview?.source === "demo" ? ` · ${t("explore_demo")}` : ""}
        </p>

        {previewLoading ? (
          <p className="explore-lede">{t("pro_demo_loading")}</p>
        ) : null}
        {previewError ? <p className="form-error">{previewError}</p> : null}
        {!previewLoading && !previewError && rows.length === 0 ? (
          <p className="explore-lede">{t("pro_demo_empty")}</p>
        ) : null}

        {rows.length > 0 ? (
          <div className="scan-list pro-demo-list">
            {rows.map((card) => (
              <Link
                key={card.id}
                href={`/cards/${encodeURIComponent(card.id)}`}
                className="scan-row radar-row radar-under"
              >
                <div className="scan-art">
                  <Image
                    src={card.image_url || "/kestrel-logo.png"}
                    alt={card.name}
                    width={48}
                    height={67}
                  />
                </div>
                <div>
                  <div className="radar-side">UNDER</div>
                  <div className="lot-name">{card.name}</div>
                  <div className="lot-meta">
                    {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
                  </div>
                </div>
                <div className="scan-metrics">
                  <strong>{formatMoney(card.spot ?? card.price)}</strong>
                  <span>fair {formatMoney(card.fair_price ?? card.predicted_price)}</span>
                  <span className="pnl-up">edge {formatChange(card.edge_pct)}</span>
                </div>
              </Link>
            ))}
          </div>
        ) : null}

        <Link href="/radar" className="btn-ghost pro-demo-cta">
          {t("pro_demo_open")}
        </Link>
      </section>

      <ul className="pro-feature-list">
        <li>{t("pro_f1")}</li>
        <li>{t("pro_f2")}</li>
        <li>{t("pro_f3")}</li>
      </ul>
    </main>
  );
}
