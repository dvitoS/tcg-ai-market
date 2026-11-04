import Link from "next/link";

export function MarketingLanding() {
  return (
    <div className="landing">
      <section className="landing-hero" aria-label="Kestrel">
        <div className="landing-hero-plane" aria-hidden>
          <img
            src="/kestrel-hero.svg"
            alt=""
            className="landing-hero-img"
            width={1920}
            height={1080}
            decoding="async"
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
