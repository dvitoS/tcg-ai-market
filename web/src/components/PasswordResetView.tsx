"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { setAccessToken, updatePasswordRequest } from "@/lib/api";

type HashSession = {
  accessToken: string;
  refreshToken: string | null;
  type: string | null;
};

function readHashSession(): HashSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return null;
  const params = new URLSearchParams(raw);
  const accessToken = params.get("access_token");
  if (!accessToken) return null;
  return {
    accessToken,
    refreshToken: params.get("refresh_token"),
    type: params.get("type"),
  };
}

export function PasswordResetView() {
  const { t } = useLocale();
  const [session, setSession] = useState<HashSession | null>(null);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const parsed = readHashSession();
    setSession(parsed);
    if (parsed?.accessToken) {
      setAccessToken(parsed.accessToken);
      // Drop secrets from the address bar after capture.
      window.history.replaceState(null, "", window.location.pathname);
    }
    setReady(true);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!session?.accessToken) return;
    if (password.length < 6) {
      setError(t("auth_password_min_error"));
      return;
    }
    if (password !== confirm) {
      setError(t("auth_password_mismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await updatePasswordRequest(password, {
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      });
      setNotice(result.message || t("auth_password_updated"));
      setPassword("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth_password_update_failed"));
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return <p className="empty-state">{t("port_loading")}</p>;
  }

  if (!session?.accessToken) {
    return (
      <section className="portfolio-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("auth_reset_eyebrow")}</p>
          <h1 className="explore-title">{t("auth_reset_missing_title")}</h1>
          <p className="explore-lede">{t("auth_reset_missing_lede")}</p>
        </div>
        <div className="detail-actions">
          <Link href="/portfolio" className="btn-primary">
            {t("auth_sign_in")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="portfolio-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("auth_reset_eyebrow")}</p>
        <h1 className="explore-title">{t("auth_reset_title")}</h1>
        <p className="explore-lede">{t("auth_reset_lede")}</p>
      </div>
      <form className="auth-card" onSubmit={onSubmit}>
        <label>
          <span>{t("auth_password_min")}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            autoComplete="new-password"
          />
        </label>
        <label>
          <span>{t("auth_password_confirm")}</span>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={6}
            autoComplete="new-password"
          />
        </label>
        {error ? <p className="banner-error">{error}</p> : null}
        {notice ? <p className="banner-ok">{notice}</p> : null}
        <div className="auth-actions">
          <button type="submit" className="btn-primary" disabled={busy}>
            {t("auth_password_save")}
          </button>
          <Link href="/portfolio" className="btn-ghost">
            {t("auth_sign_in")}
          </Link>
        </div>
      </form>
    </section>
  );
}
