"use client";

import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";

const DISMISS_KEY = "kestrel_pwa_install_dismissed";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const mq = window.matchMedia("(display-mode: standalone)").matches;
  const ios = "standalone" in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
  return mq || ios;
}

function isIosSafari(): boolean {
  if (typeof window === "undefined") return false;
  const ua = window.navigator.userAgent;
  const iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const webkit = /WebKit/.test(ua);
  const criOS = /CriOS|FxiOS|EdgiOS/.test(ua);
  return iOS && webkit && !criOS;
}

export function PwaChrome() {
  const { t } = useLocale();
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIos, setShowIos] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    // Avoid SW cache fights during local Next HMR.
    if (process.env.NODE_ENV !== "production") return;
    void navigator.serviceWorker.register("/sw.js").catch(() => {
      /* installable desk is best-effort */
    });
  }, []);

  useEffect(() => {
    if (isStandalone()) return;
    try {
      if (window.localStorage.getItem(DISMISS_KEY) === "1") return;
    } catch {
      /* ignore */
    }

    function onBip(event: Event) {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
      setVisible(true);
    }
    window.addEventListener("beforeinstallprompt", onBip);

    if (isIosSafari()) {
      setShowIos(true);
      setVisible(true);
    }

    return () => window.removeEventListener("beforeinstallprompt", onBip);
  }, []);

  if (!visible) return null;

  function dismiss() {
    setVisible(false);
    setDeferred(null);
    try {
      window.localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    try {
      await deferred.userChoice;
    } catch {
      /* ignore */
    }
    setDeferred(null);
    setVisible(false);
  }

  return (
    <div className="pwa-install" role="region" aria-label={t("pwa_install_title")}>
      <div className="pwa-install-body">
        <strong>{t("pwa_install_title")}</strong>
        <p>{showIos && !deferred ? t("pwa_install_ios") : t("pwa_install_lede")}</p>
      </div>
      <div className="pwa-install-actions">
        {deferred ? (
          <button type="button" className="btn-primary" onClick={() => void install()}>
            {t("pwa_install_cta")}
          </button>
        ) : null}
        <button type="button" className="btn-ghost" onClick={dismiss}>
          {t("pwa_install_dismiss")}
        </button>
      </div>
    </div>
  );
}
