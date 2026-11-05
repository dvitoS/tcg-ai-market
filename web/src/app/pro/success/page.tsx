"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchBillingMe } from "@/lib/api";

export default function ProSuccessPage() {
  const { t } = useLocale();
  const { user, loading } = useAuth();
  const [isPro, setIsPro] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchBillingMe();
      setIsPro(Boolean(me.is_pro));
    } catch {
      setIsPro(null);
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    void refresh();
  }, [loading, user, refresh]);

  return (
    <main className="pro-success-page">
      <p className="explore-command-eyebrow">Soft Pro</p>
      <h1 className="explore-title">
        {isPro ? t("pro_success_active_title") : t("pro_success_title")}
      </h1>
      <p className="explore-lede">
        {isPro
          ? t("pro_success_active_lede")
          : t("pro_success_lede")}
      </p>
      <div className="detail-actions">
        <Link href="/radar" className="btn-primary">
          {t("pro_open_radar")}
        </Link>
        <Link href="/trade" className="btn-ghost">
          {t("pro_open_trade")}
        </Link>
        <Link href="/dealer" className="btn-ghost">
          {t("pro_open_dealer")}
        </Link>
        <Link href="/pro" className="btn-ghost">
          {t("pro_status_link")}
        </Link>
        <Link href="/portfolio" className="btn-ghost">
          {user ? t("nav_portfolio") : t("auth_sign_in")}
        </Link>
      </div>
    </main>
  );
}
