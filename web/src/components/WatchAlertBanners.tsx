"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchWatchlistAlerts } from "@/lib/api";
import type { WatchAlertItem } from "@/lib/types";
import {
  ALERT_DISMISS_KEY,
  ALERT_PREFS_EVENT,
  ALERT_SURE_KEY,
  ALERT_THRESHOLD_KEY,
  dismissAlert,
  readDismissed,
  readSureOnly,
  readThresholdPct,
} from "@/lib/watchAlertPrefs";

const BANNER_LIMIT = 5;

export function WatchAlertBanners() {
  const { user, loading } = useAuth();
  const { t } = useLocale();
  const pathname = usePathname();
  // Portfolio already loads its own alert digest — skip a duplicate request.
  const skipFetch = Boolean(pathname?.startsWith("/portfolio"));
  const [alerts, setAlerts] = useState<WatchAlertItem[]>([]);

  const refresh = useCallback(async () => {
    if (!user || skipFetch) {
      setAlerts([]);
      return;
    }
    const dismissedIds = readDismissed();
    const threshold = readThresholdPct();
    let sureOnly = readSureOnly();
    try {
      let digest = await fetchWatchlistAlerts({
        threshold_pct: threshold,
        sure_only: sureOnly,
        dismissed: dismissedIds,
      });
      if (sureOnly && !digest.sure_only_allowed) {
        sureOnly = false;
        digest = await fetchWatchlistAlerts({
          threshold_pct: threshold,
          sure_only: false,
          dismissed: dismissedIds,
        });
      }
      setAlerts(digest.items.slice(0, BANNER_LIMIT));
    } catch {
      setAlerts([]);
    }
  }, [user, skipFetch]);

  useEffect(() => {
    if (loading) return;
    void refresh();
  }, [loading, refresh]);

  useEffect(() => {
    function onPrefs() {
      void refresh();
    }
    function onStorage(event: StorageEvent) {
      if (
        event.key === ALERT_DISMISS_KEY ||
        event.key === ALERT_THRESHOLD_KEY ||
        event.key === ALERT_SURE_KEY
      ) {
        void refresh();
      }
    }
    window.addEventListener(ALERT_PREFS_EVENT, onPrefs);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(ALERT_PREFS_EVENT, onPrefs);
      window.removeEventListener("storage", onStorage);
    };
  }, [refresh]);

  if (!user || alerts.length === 0) return null;

  return (
    <div className="watch-alert-banners" aria-live="polite">
      {alerts.map((alert) => (
        <div
          key={alert.card_id}
          className={`watch-alert-banner${alert.sure ? " is-sure" : ""}`}
        >
          <Link
            href={`/cards/${encodeURIComponent(alert.card_id)}`}
            className="watch-alert-banner-body"
          >
            {alert.sure ? "✓ " : ""}
            {alert.body}
          </Link>
          <button
            type="button"
            className="btn-ghost watch-alert-banner-dismiss"
            onClick={() => {
              dismissAlert(alert.card_id);
              setAlerts((prev) =>
                prev.filter((row) => row.card_id !== alert.card_id),
              );
            }}
          >
            {t("alert_dismiss")}
          </button>
        </div>
      ))}
    </div>
  );
}
