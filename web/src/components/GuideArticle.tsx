import Link from "next/link";

import type { Guide } from "@/lib/guides";
import { guidePath } from "@/lib/guides";
import { guideJsonLd } from "@/lib/seo";

export function GuideArticle({ guide }: { guide: Guide }) {
  const jsonLd = guideJsonLd(guide);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article className="guide-page">
        <nav className="guide-crumb" aria-label="Breadcrumb">
          <Link href="/">Kestrel</Link>
          <span aria-hidden>/</span>
          <Link href="/guides">Guides</Link>
          <span aria-hidden>/</span>
          <span>{guide.eyebrow}</span>
        </nav>

        <header className="guide-header">
          <p className="explore-command-eyebrow">{guide.eyebrow}</p>
          <h1 className="guide-title">{guide.title}</h1>
          <p className="guide-lede">{guide.lede}</p>
        </header>

        <div className="guide-prose">
          {guide.sections.map((section) => (
            <section key={section.heading} className="guide-section">
              <h2>{section.heading}</h2>
              {section.body.map((para) => (
                <p key={para.slice(0, 48)}>{para}</p>
              ))}
            </section>
          ))}
        </div>

        {guide.faqs.length > 0 ? (
          <section className="guide-faq" aria-labelledby="guide-faq-title">
            <h2 id="guide-faq-title">FAQ</h2>
            <dl>
              {guide.faqs.map((faq) => (
                <div key={faq.question} className="guide-faq-item">
                  <dt>{faq.question}</dt>
                  <dd>{faq.answer}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        <div className="detail-actions guide-actions">
          <Link href={guide.primaryCta.href} className="btn-primary">
            {guide.primaryCta.label}
          </Link>
          {guide.secondaryCta ? (
            <Link href={guide.secondaryCta.href} className="btn-ghost">
              {guide.secondaryCta.label}
            </Link>
          ) : null}
        </div>

        <p className="guide-more">
          More Soft Ink guides:{" "}
          <Link href="/guides">all guides</Link>
          {" · "}
          <Link href={guidePath("pokemon-tcg-fair-value")}>fair value</Link>
          {" · "}
          <Link href={guidePath("should-i-grade")}>grading</Link>
          {" · "}
          <Link href={guidePath("trade-fairness")}>trade fairness</Link>
        </p>
      </article>
    </>
  );
}
