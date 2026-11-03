"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { href: "/", label: "Browse" },
  { href: "/#signals", label: "AI signals" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scanner", label: "Scanner" },
  { href: "/dealer", label: "Dealer" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const { user, logout, ensureDemoSession } = useAuth();

  return (
    <header className="site-header">
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
      <nav className="site-nav" aria-label="Primary">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          if ("soon" in item && item.soon) {
            return (
              <span
                key={item.href}
                className="nav-link is-soon"
                title="Coming in the web rewrite"
              >
                {item.label}
              </span>
            );
          }
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${active ? "is-active" : ""}`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="header-actions">
        <span className="tagline">Spot. Signal. Act.</span>
        {user ? (
          <button type="button" className="btn-ghost header-auth" onClick={logout}>
            {user.email || "Account"}
          </button>
        ) : (
          <button
            type="button"
            className="btn-ghost header-auth"
            onClick={() => void ensureDemoSession()}
          >
            Sign in
          </button>
        )}
      </div>
    </header>
  );
}
