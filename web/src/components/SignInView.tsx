"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { forgotPasswordRequest } from "@/lib/api";

type AuthMode = "signin" | "signup" | "forgot";

type Props = {
  /** Where to send the user after a successful session (safe relative path). */
  nextPath?: string | null;
  onAuthenticated: () => void | Promise<void>;
};

export function SignInView({ nextPath, onAuthenticated }: Props) {
  const { t } = useLocale();
  const router = useRouter();
  const { login, signup } = useAuth();
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const title =
    authMode === "signup"
      ? t("auth_create_account")
      : authMode === "forgot"
        ? t("auth_forgot_title")
        : t("auth_sign_in");
  const lede =
    authMode === "signup"
      ? t("auth_signup_lede")
      : authMode === "forgot"
        ? t("auth_forgot_lede")
        : t("auth_signin_lede");

  async function finishAuthenticated() {
    if (nextPath) {
      router.replace(nextPath);
      return;
    }
    await onAuthenticated();
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (authMode === "forgot") {
        const origin =
          typeof window !== "undefined" ? window.location.origin : "";
        const result = await forgotPasswordRequest(
          email.trim(),
          origin ? `${origin}/auth/reset` : undefined,
        );
        setNotice(result.message || t("auth_forgot_sent"));
        return;
      }
      if (authMode === "signup") {
        const outcome = await signup(email.trim(), password);
        if (outcome.needsConfirmation) {
          setNotice(
            outcome.message || t("auth_signup_confirm"),
          );
          setAuthMode("signin");
          return;
        }
        setNotice(outcome.message || t("auth_signup_ok"));
      } else {
        await login(email.trim(), password);
      }
      await finishAuthenticated();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : authMode === "signup"
            ? t("auth_signup_failed")
            : authMode === "forgot"
              ? t("auth_forgot_failed")
              : t("auth_signin_failed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-page">
      <div className="auth-atmosphere" aria-hidden>
        <div className="auth-glow auth-glow-a" />
        <div className="auth-glow auth-glow-b" />
        <div className="auth-grain" />
      </div>

      <div className="auth-stage">
        <p className="auth-brand">Kestrel</p>
        <h1 className="auth-title">{title}</h1>
        <p className="auth-lede">{lede}</p>

        <form className="auth-form" onSubmit={onSubmit}>
          {authMode !== "forgot" ? (
            <div className="auth-mode-toggle" role="tablist" aria-label={t("auth_mode")}>
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "signin"}
                className={authMode === "signin" ? "is-active" : undefined}
                disabled={busy}
                onClick={() => {
                  setAuthMode("signin");
                  setError(null);
                  setNotice(null);
                }}
              >
                {t("auth_sign_in")}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "signup"}
                className={authMode === "signup" ? "is-active" : undefined}
                disabled={busy}
                onClick={() => {
                  setAuthMode("signup");
                  setError(null);
                  setNotice(null);
                }}
              >
                {t("auth_create_account")}
              </button>
            </div>
          ) : null}

          <label>
            <span>{t("auth_email")}</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              autoFocus
              placeholder="you@email.com"
            />
          </label>

          {authMode !== "forgot" ? (
            <label>
              <span className="auth-label-row">
                <span>
                  {authMode === "signup" ? t("auth_password_min") : t("auth_password")}
                </span>
                {authMode === "signin" ? (
                  <button
                    type="button"
                    className="auth-inline-link"
                    disabled={busy}
                    onClick={() => {
                      setAuthMode("forgot");
                      setError(null);
                      setNotice(null);
                    }}
                  >
                    {t("auth_forgot")}
                  </button>
                ) : null}
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={authMode === "signup" ? 6 : undefined}
                autoComplete={
                  authMode === "signup" ? "new-password" : "current-password"
                }
              />
            </label>
          ) : null}

          {error ? <p className="banner-error">{error}</p> : null}
          {notice ? <p className="banner-ok">{notice}</p> : null}

          <div className="auth-actions">
            <button type="submit" className="btn-primary auth-submit" disabled={busy}>
              {authMode === "signup"
                ? t("auth_create_account")
                : authMode === "forgot"
                  ? t("auth_forgot_submit")
                  : t("auth_sign_in")}
            </button>
            {authMode === "forgot" ? (
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => {
                  setAuthMode("signin");
                  setError(null);
                  setNotice(null);
                }}
              >
                {t("auth_forgot_back")}
              </button>
            ) : null}
          </div>

        </form>

        <p className="auth-foot">
          <Link href="/browse" className="auth-foot-link">
            {t("auth_browse_market")}
          </Link>
        </p>
      </div>
    </section>
  );
}
