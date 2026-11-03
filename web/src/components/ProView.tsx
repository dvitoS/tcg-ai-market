import Link from "next/link";

export function ProView({
  checkoutUrl,
  proOpen,
  error,
}: {
  checkoutUrl: string | null;
  proOpen: boolean;
  error?: string | null;
}) {
  return (
    <main className="pro-page">
      <p className="explore-command-eyebrow">Kestrel Pro</p>
      <h1 className="explore-title">Dealer desk + sure signals</h1>
      <p className="explore-lede">
        Soft Pro unlocks inventory scoring, fee-aware LIST / BUY MORE, and higher-confidence
        alert surfaces. €7/mo after a 7-day trial via Creem.
      </p>

      {error ? <p className="banner-error">{error}</p> : null}

      {proOpen ? (
        <p className="pro-open-note">
          Open beta is still on — Pro surfaces are unlocked for everyone. Checkout stays ready
          for when we flip the gate.
        </p>
      ) : (
        <p className="pro-open-note">Pro is gated. Upgrade with the same email you use to sign in.</p>
      )}

      <div className="detail-actions">
        {checkoutUrl ? (
          <a href={checkoutUrl} className="btn-primary" rel="noreferrer">
            Upgrade with Creem
          </a>
        ) : (
          <span className="btn-ghost is-disabled" aria-disabled="true">
            Checkout link not configured
          </span>
        )}
        <Link href="/dealer" className="btn-ghost">
          Open Dealer desk
        </Link>
        <Link href="/portfolio" className="btn-ghost">
          Sign in
        </Link>
      </div>

      <ul className="pro-feature-list">
        <li>CSV inventory × market board with sell fee + shipping</li>
        <li>Conformal-gated LIST / BUY MORE actions</li>
        <li>Entitlement tied to your checkout email after payment</li>
      </ul>
    </main>
  );
}
