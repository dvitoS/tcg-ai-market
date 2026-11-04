"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { href: "/", label: "Browse" },
  { href: "/#signals", label: "AI signals" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scanner", label: "Scanner" },
  { href: "/dealer", label: "Dealer" },
  { href: "/pro", label: "Pro" },
] as const;

function linkActive(pathname: string, href: string): boolean {
  if (href === "/" || href.startsWith("/#")) {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuId = useId();

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

      <nav className="site-nav site-nav-desktop" aria-label="Primary">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="header-actions">
        <span className="tagline">Spot. Signal. Act.</span>
        {user ? (
          <button type="button" className="btn-ghost header-auth" onClick={logout}>
            {user.email || "Account"}
          </button>
        ) : (
          <Link href="/portfolio" className="btn-ghost header-auth">
            Sign in
          </Link>
        )}
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? "Close menu" : "Open menu"}
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
        <nav className="site-nav-mobile" aria-label="Mobile">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${linkActive(pathname, item.href) ? "is-active" : ""}`}
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
          {user ? (
            <button
              type="button"
              className="btn-ghost nav-mobile-auth"
              onClick={() => {
                setOpen(false);
                logout();
              }}
            >
              Sign out · {user.email || "Account"}
            </button>
          ) : (
            <Link
              href="/portfolio"
              className="btn-primary nav-mobile-auth"
              onClick={() => setOpen(false)}
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
      {open ? (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      ) : null}
    </header>
  );
}
