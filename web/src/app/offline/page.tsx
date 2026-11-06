import Link from "next/link";

export const metadata = {
  title: "Offline — Kestrel",
  robots: { index: false, follow: false },
};

export default function OfflinePage() {
  return (
    <div className="offline-page">
      <p className="eyebrow">Kestrel</p>
      <h1>You’re offline</h1>
      <p>
        Soft Ink needs a connection for live spots and signals. Reconnect, then
        open the desk again.
      </p>
      <Link href="/" className="btn-primary">
        Back to Kestrel
      </Link>
    </div>
  );
}
