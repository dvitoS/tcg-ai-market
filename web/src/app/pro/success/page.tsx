import Link from "next/link";

export default function ProSuccessPage() {
  return (
    <main className="pro-success-page">
      <p className="explore-command-eyebrow">Soft Pro</p>
      <h1 className="explore-title">You&apos;re in</h1>
      <p className="explore-lede">
        Payment received. Sign in with the same email you used at checkout so Dealer desk
        unlocks on this account.
      </p>
      <div className="detail-actions">
        <Link href="/dealer" className="btn-primary">
          Open Dealer desk
        </Link>
        <Link href="/portfolio" className="btn-ghost">
          Portfolio
        </Link>
      </div>
    </main>
  );
}
