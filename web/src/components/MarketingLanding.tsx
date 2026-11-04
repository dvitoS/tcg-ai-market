import Image from "next/image";
import Link from "next/link";

type Props = {
  heroImageUrl?: string | null;
  heroCardName?: string | null;
};

export function MarketingLanding({ heroImageUrl, heroCardName }: Props) {
  const hasArt = Boolean(heroImageUrl);
  const art = heroImageUrl || "/kestrel-logo.png";
  const artAlt = heroCardName
    ? `${heroCardName} — market art`
    : "Kestrel";

  return (
    <div className="landing">
      <section className="landing-hero" aria-label="Kestrel">
        <div
          className={`landing-hero-plane${hasArt ? "" : " is-fallback"}`}
          aria-hidden={!hasArt}
        >
          <Image
            src={art}
            alt={artAlt}
            fill
            priority
            sizes="100vw"
            className={`landing-hero-img${hasArt ? "" : " is-mark"}`}
          />
          <div className="landing-hero-veil" />
        </div>

        <div className="landing-hero-copy">
          <p className="landing-brand">Kestrel</p>
          <h1 className="landing-headline">Spot. Signal. Act.</h1>
          <p className="landing-lede">
            Pokémon TCG market prices and AI forecasts — browse, watch, and
            move before the print run cools.
          </p>
          <div className="landing-ctas">
            <Link href="/browse" className="btn-primary landing-cta">
              Open market
            </Link>
            <Link href="/pro" className="btn-ghost landing-cta">
              Soft Pro
            </Link>
          </div>
        </div>
      </section>

      <section className="landing-follow" aria-labelledby="landing-follow-title">
        <h2 id="landing-follow-title" className="landing-follow-title">
          From signal to desk
        </h2>
        <p className="landing-follow-lede">
          One path: browse the board, read the AI explain, hold a portfolio,
          scan movers, export dealer CSV.
        </p>
        <Link href="/browse#signals" className="landing-follow-link">
          Jump to AI signals →
        </Link>
      </section>
    </div>
  );
}
