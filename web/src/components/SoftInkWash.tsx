/**
 * Soft Ink hero atmosphere — wet copper blooms + drifting ink beads.
 * Deliberately not a particle/neon field (avoids looking like tcginvest).
 */
export function SoftInkWash() {
  return (
    <div className="soft-ink-wash" aria-hidden="true">
      <div className="soft-ink-wash-haze" />
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-a" />
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-b" />
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-c" />
      <div className="soft-ink-wash-fiber" />
      <span className="soft-ink-bead soft-ink-bead-1" />
      <span className="soft-ink-bead soft-ink-bead-2" />
      <span className="soft-ink-bead soft-ink-bead-3" />
      <span className="soft-ink-bead soft-ink-bead-4" />
      <svg
        className="soft-ink-wash-mark"
        viewBox="0 0 640 360"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="soft-ink-tide" x1="0%" y1="50%" x2="100%" y2="50%">
            <stop offset="0%" stopColor="rgba(192,122,58,0)" />
            <stop offset="45%" stopColor="rgba(212,165,116,0.55)" />
            <stop offset="100%" stopColor="rgba(192,122,58,0)" />
          </linearGradient>
        </defs>
        <path
          className="soft-ink-wash-tide"
          d="M-40 210 C 80 160, 180 250, 300 190 S 480 140, 700 220"
          fill="none"
          stroke="url(#soft-ink-tide)"
          strokeWidth="28"
          strokeLinecap="round"
          opacity="0.55"
        />
        <path
          className="soft-ink-wash-stroke"
          d="M48 278 C 150 236, 250 308, 360 248 S 540 200, 620 262"
          fill="none"
          stroke="rgba(212,165,116,0.55)"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
