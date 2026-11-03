import Image from "next/image";
import Link from "next/link";

const NAV = [
  { href: "/", label: "Browse" },
  { href: "/#signals", label: "AI signals" },
  { href: "/portfolio", label: "Portfolio", soon: true },
  { href: "/scanner", label: "Scanner", soon: true },
  { href: "/dealer", label: "Dealer", soon: true },
] as const;

export function SiteHeader() {
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
        {NAV.map((item) =>
          "soon" in item && item.soon ? (
            <span key={item.href} className="nav-link is-soon" title="Coming in the web rewrite">
              {item.label}
            </span>
          ) : (
            <Link key={item.href} href={item.href} className="nav-link">
              {item.label}
            </Link>
          ),
        )}
      </nav>
      <div className="header-actions">
        <span className="tagline">Spot. Signal. Act.</span>
      </div>
    </header>
  );
}
