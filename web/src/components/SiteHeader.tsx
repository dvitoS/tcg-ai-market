"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { CurrencySwitcher } from "@/components/CurrencySwitcher";
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
  const [moreOpen, setMoreOpen] = useState(false);
  const menuId = useId();
  const moreMenuId = useId();
  const moreRef = useRef<HTMLDivElement>(null);

  // Free tools first — Pro desks live under More; Pro CTA sits with auth.
  const freeNav = useMemo<NavItem[]>(
    () => [
      { href: "/browse", labelKey: "nav_browse" },
      { href: "/identify", labelKey: "nav_identify" },
      { href: "/sealed", labelKey: "nav_sealed" },
      { href: "/binder", labelKey: "nav_binder" },
      { href: "/portfolio", labelKey: "nav_portfolio" },
    ],
    [],
  );

  const proNav = useMemo<NavItem[]>(
    () => [
      { href: "/radar", labelKey: "nav_radar" },
      { href: "/trade", labelKey: "nav_trade" },
      { href: "/scanner", labelKey: "nav_scanner" },
      { href: "/dealer", labelKey: "nav_dealer" },
    ],
    [],
  );

  useEffect(() => {
    setOpen(false);
    setMoreOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open && !moreOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        setMoreOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, moreOpen]);

  useEffect(() => {
    if (!moreOpen) return;
    function onPointerDown(event: MouseEvent | PointerEvent) {
      const root = moreRef.current;
      if (!root) return;
      if (event.target instanceof Node && !root.contains(event.target)) {
        setMoreOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [moreOpen]);

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
      <Link href="/" className="brand" aria-label="Kestrel home" title={t("brand_tagline")}>
        <Image
          src="/kestrel-mark.png"
          alt=""
          width={40}
          height={40}
          className="brand-mark"
          priority
        />
        <span className="brand-name">Kestrel</span>
      </Link>

      <nav className="site-nav site-nav-desktop" aria-label={t("nav_primary")}>
        {freeNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
          >
            {t(item.labelKey)}
          </Link>
        ))}
        <div
          className={`nav-more${moreOpen ? " is-open" : ""}`}
          ref={moreRef}
        >
          <button
            type="button"
            className="nav-link nav-more-summary"
            aria-expanded={moreOpen}
            aria-haspopup="menu"
            aria-controls={moreMenuId}
            onClick={() => setMoreOpen((value) => !value)}
          >
            {t("nav_more")}
          </button>
          {moreOpen ? (
            <div
              id={moreMenuId}
              className="nav-more-menu"
              role="menu"
              aria-label={t("nav_pro_section")}
            >
              <p className="nav-more-label">{t("nav_pro_section")}</p>
              {proNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  role="menuitem"
                  className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
                  onClick={() => setMoreOpen(false)}
                >
                  {t(item.labelKey)}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </nav>

      <div className="header-actions">
        <LocaleSwitcher />
        <CurrencySwitcher />
        <Link
          href="/pro"
          className={`btn-ghost header-pro${linkActive(pathname, "/pro") ? " is-active" : ""}`}
        >
          {t("nav_pro")}
        </Link>
        {user ? (
          <button type="button" className="btn-ghost header-auth" onClick={logout}>
            {user.email || t("auth_sign_out")}
          </button>
        ) : (
          <Link href="/signin" className="btn-ghost header-auth">
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
          <p className="nav-mobile-section">{t("nav_free_section")}</p>
          {freeNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
              onClick={() => setOpen(false)}
            >
              {t(item.labelKey)}
            </Link>
          ))}
          <p className="nav-mobile-section">{t("nav_pro_section")}</p>
          {proNav.map((item) => (
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
            <CurrencySwitcher />
          </div>
          <div className="nav-mobile-auth-row">
            <Link
              href="/pro"
              className="btn-ghost header-pro"
              onClick={() => setOpen(false)}
            >
              {t("nav_pro")}
            </Link>
            {user ? (
              <button
                type="button"
                className="btn-ghost nav-mobile-auth"
                onClick={() => {
                  setOpen(false);
                  logout();
                }}
              >
                {t("auth_sign_out")}
                {user.email ? ` · ${user.email}` : ""}
              </button>
            ) : (
              <>
                <Link
                  href="/signin"
                  className="btn-primary"
                  onClick={() => setOpen(false)}
                >
                  {t("auth_sign_in")}
                </Link>
                <Link
                  href="/signin?auth=signup"
                  className="btn-ghost"
                  onClick={() => setOpen(false)}
                >
                  {t("auth_create_account")}
                </Link>
              </>
            )}
          </div>
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
