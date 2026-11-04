"use client";

import Link from "next/link";

import { useLocale } from "@/components/LocaleProvider";

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

  return (
    <main className="pro-page">
      <p className="explore-command-eyebrow">{t("pro_eyebrow")}</p>
      <h1 className="explore-title">{t("pro_title")}</h1>
      <p className="explore-lede">{t("pro_lede")}</p>

      {error ? <p className="banner-error">{error}</p> : null}

      {proOpen ? (
        <p className="pro-open-note">{t("pro_open_note")}</p>
      ) : (
        <p className="pro-open-note">{t("pro_gated_note")}</p>
      )}

      <div className="detail-actions">
        {checkoutUrl ? (
          <a href={checkoutUrl} className="btn-primary" rel="noreferrer">
            {t("dealer_upgrade")}
          </a>
        ) : (
          <span className="btn-ghost is-disabled" aria-disabled="true">
            {t("pro_checkout_missing")}
          </span>
        )}
        <Link href="/dealer" className="btn-ghost">
          {t("pro_open_dealer")}
        </Link>
        <Link href="/portfolio" className="btn-ghost">
          {t("auth_sign_in")}
        </Link>
      </div>

      <ul className="pro-feature-list">
        <li>{t("pro_f1")}</li>
        <li>{t("pro_f2")}</li>
        <li>{t("pro_f3")}</li>
      </ul>
    </main>
  );
}
