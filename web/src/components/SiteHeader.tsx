"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { useLocale } from "@/components/LocaleProvider";
import type { MessageKey } from "@/lib/i18n/messages";

type NavItem = { href: string; labelKey: MessageKey };

function linkActive(pathname: string, href: string): boolean {
  if (href.startsWith("/browse")) {
    return pathname === "/browse" || pathname.startsWith("/browse/");
  }
  const path = href.split("#")[0];
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function SiteHeader() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const menuId = useId();

  const nav = useMemo<NavItem[]>(
    () => [
      { href: "/browse", labelKey: "nav_browse" },
      { href: "/browse#signals", labelKey: "nav_signals" },
      { href: "/portfolio", labelKey: "nav_portfolio" },
      { href: "/scanner", labelKey: "nav_scanner" },
      { href: "/radar", labelKey: "nav_radar" },
      { href: "/trade", labelKey: "nav_trade" },
      { href: "/dealer", labelKey: "nav_dealer" },
      { href: "/pro", labelKey: "nav_pro" },
    ],
    [],
  );

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <header className={`site-header${open ? " is-nav-open" : ""}`}>
      <Link href="/" className="brand" aria-label="Kestrel home">
        <Image
          src="/kestrel-logo.png"
          alt=""
          width={40}
          height={40}
          className="brand-mark"
          priority
          style={{ width: 36, height: 36, objectFit: "contain" }}
        />
        <span className="brand-name">Kestrel</span>
      </Link>

      <nav className="site-nav site-nav-desktop" aria-label={t("nav_primary")}>
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
          >
            {t(item.labelKey)}
          </Link>
        ))}
      </nav>

      <div className="header-actions">
        <LocaleSwitcher />
        <span className="tagline">{t("brand_tagline")}</span>
        {user ? (
          <button type="button" className="btn-ghost header-auth" onClick={logout}>
            {user.email || t("auth_sign_out")}
          </button>
        ) : (
          <Link href="/portfolio" className="btn-ghost header-auth">
            {t("auth_sign_in")}
          </Link>
        )}
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? t("nav_close_menu") : t("nav_open_menu")}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="nav-toggle-bar" />
          <span className="nav-toggle-bar" />
          <span className="nav-toggle-bar" />
        </button>
      </div>

      <div
        id={menuId}
        className={`site-nav-drawer${open ? " is-open" : ""}`}
        hidden={!open}
      >
        <nav className="site-nav-mobile" aria-label={t("nav_mobile")}>
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
              onClick={() => setOpen(false)}
            >
              {t(item.labelKey)}
            </Link>
          ))}
          <div className="nav-mobile-locale">
            <LocaleSwitcher />
          </div>
          {user ? (
            <button
              type="button"
              className="btn-ghost nav-mobile-auth"
              onClick={() => {
                setOpen(false);
                logout();
              }}
            >
              {t("auth_sign_out")} · {user.email || "Account"}
            </button>
          ) : (
            <Link
              href="/portfolio"
              className="btn-primary nav-mobile-auth"
              onClick={() => setOpen(false)}
            >
              {t("auth_sign_in")}
            </Link>
          )}
        </nav>
      </div>
      {open ? (
        <button
          type="button"
          className="nav-backdrop"
          aria-label={t("nav_close_menu")}
          onClick={() => setOpen(false)}
        />
      ) : null}
    </header>
  );
}
