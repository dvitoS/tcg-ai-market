import type { Metadata } from "next";
import Link from "next/link";

import { GUIDES, guidePath } from "@/lib/guides";
import { absoluteUrl } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Pokémon card guides — good price, grading, trades",
  description:
    "Guides: what a good price means, should you grade, and how to judge trade fairness with Kestrel.",
  alternates: { canonical: absoluteUrl("/guides") },
};

export default function GuidesIndexPage() {
  return (
    <main className="guide-page">
      <nav className="guide-crumb" aria-label="Breadcrumb">
        <Link href="/">Kestrel</Link>
        <span aria-hidden>/</span>
        <span>Guides</span>
      </nav>

      <header className="guide-header">
        <p className="explore-command-eyebrow">Guides</p>
        <h1 className="guide-title">Pokémon TCG decision guides</h1>
        <p className="guide-lede">
          Plain-language explainers for good price, grading, and trade
          fairness — the same words Kestrel uses on deals and trade checks.
        </p>
      </header>

      <nav className="guide-index" aria-label="Guide list">
        {GUIDES.map((guide) => (
          <Link
            key={guide.slug}
            href={guidePath(guide.slug)}
            className="guide-index-link"
          >
            <span className="guide-index-title">{guide.title}</span>
            <span className="guide-index-meta">{guide.description}</span>
          </Link>
        ))}
      </nav>
    </main>
  );
}
