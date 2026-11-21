"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchBillingStatus } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";

const STORAGE_KEY = "kestrel_open_beta_promo_v1";
const DISMISS_DAYS = 7;

function wasDismissedRecently(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const until = Number(raw);
    if (!Number.isFinite(until)) return false;
    return Date.now() < until;
  } catch {
    return false;
  }
}

function rememberDismiss() {
  if (typeof window === "undefined") return;
  try {
    const until = Date.now() + DISMISS_DAYS * 24 * 60 * 60 * 1000;
    window.localStorage.setItem(STORAGE_KEY, String(until));
  } catch {
    /* ignore */
  }
}

export function OpenBetaPromo() {
  const { t } = useLocale();
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (wasDismissedRecently()) return;
    let alive = true;
    let showTimer: ReturnType<typeof setTimeout> | undefined;
    let enterTimer: ReturnType<typeof setTimeout> | undefined;

    void fetchBillingStatus()
      .then((status) => {
        if (!alive || !status.pro_open) return;
        // Let the hero paint first, then bring the promo in.
        showTimer = setTimeout(() => {
          if (!alive) return;
          setOpen(true);
          enterTimer = setTimeout(() => {
            if (alive) setVisible(true);
          }, 40);
        }, 900);
      })
      .catch(() => {
        /* stay quiet if billing status is down */
      });

    return () => {
      alive = false;
      if (showTimer) clearTimeout(showTimer);
      if (enterTimer) clearTimeout(enterTimer);
    };
  }, []);

  function dismiss() {
    rememberDismiss();
    setVisible(false);
    window.setTimeout(() => setOpen(false), 220);
  }

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") dismiss();
    }
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className={`beta-promo${visible ? " is-visible" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <button
        type="button"
        className="beta-promo-backdrop"
        aria-label={t("landing_beta_dismiss")}
        onClick={dismiss}
      />
      <div className="beta-promo-panel">
        <p className="beta-promo-eyebrow">{t("landing_beta_eyebrow")}</p>
        <h2 id={titleId} className="beta-promo-title">
          {t("landing_beta_title")}
        </h2>
        <p className="beta-promo-lede">{t("landing_beta_lede")}</p>
        <div className="beta-promo-actions">
          <Link
            href="/radar"
            className="btn-primary"
            onClick={() => {
              trackFunnel("landing_cta_pro", { source: "open_beta_promo" });
              rememberDismiss();
            }}
          >
            {t("landing_beta_cta_deals")}
          </Link>
          <Link
            href="/portfolio?auth=signin"
            className="btn-ghost"
            onClick={() => {
              trackFunnel("landing_cta_pro", { source: "open_beta_promo_signin" });
              rememberDismiss();
            }}
          >
            {t("landing_beta_cta_signin")}
          </Link>
        </div>
        <button
          type="button"
          className="beta-promo-close"
          onClick={dismiss}
        >
          {t("landing_beta_dismiss")}
        </button>
      </div>
    </div>
  );
}
