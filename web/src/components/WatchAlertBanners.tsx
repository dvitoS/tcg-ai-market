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

/** One banner max — stack was crowding the first viewport. */
const BANNER_LIMIT = 1;

export function WatchAlertBanners() {
  const { user, loading } = useAuth();
  const { t } = useLocale();
  const pathname = usePathname();
  // Marketing + upgrade pitch + portfolio digest already cover alerts.
  const skipFetch =
    pathname === "/" ||
    Boolean(pathname?.startsWith("/portfolio")) ||
    Boolean(pathname?.startsWith("/pro"));
  const [alerts, setAlerts] = useState<WatchAlertItem[]>([]);
  const [extra, setExtra] = useState(0);

  const refresh = useCallback(async () => {
    if (!user || skipFetch) {
      setAlerts([]);
      setExtra(0);
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
      const items = digest.items || [];
      setAlerts(items.slice(0, BANNER_LIMIT));
      setExtra(Math.max(0, items.length - BANNER_LIMIT));
    } catch {
      setAlerts([]);
      setExtra(0);
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

  // Let PWA defer while a watch banner owns the chrome slot.
  useEffect(() => {
    try {
      if (alerts.length > 0) {
        window.sessionStorage.setItem("kestrel_watch_banner", "1");
      } else {
        window.sessionStorage.removeItem("kestrel_watch_banner");
      }
      window.dispatchEvent(new Event("kestrel-watch-banner"));
    } catch {
      /* ignore */
    }
  }, [alerts.length]);

  if (!user || alerts.length === 0) return null;

  const alert = alerts[0];

  return (
    <div className="watch-alert-banners" aria-live="polite">
      <div
        className={`watch-alert-banner${alert.sure ? " is-sure" : ""}`}
      >
        <Link
          href={`/cards/${encodeURIComponent(alert.card_id)}`}
          className="watch-alert-banner-body"
        >
          {alert.sure ? "✓ " : ""}
          {alert.body}
          {extra > 0 ? ` · ${t("alert_banner_extra", { n: String(extra) })}` : ""}
        </Link>
        <div className="watch-alert-banner-actions">
          {extra > 0 ? (
            <Link href="/portfolio#watchlist" className="btn-ghost watch-alert-banner-dismiss">
              {t("alert_see_all")}
            </Link>
          ) : null}
          <button
            type="button"
            className="btn-ghost watch-alert-banner-dismiss"
            onClick={() => {
              dismissAlert(alert.card_id);
              setAlerts([]);
              void refresh();
            }}
          >
            {t("alert_dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
