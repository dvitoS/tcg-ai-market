/** Soft Ink hero atmosphere — paper fiber + copper ink bloom (not a particle field). */
export function SoftInkWash() {
  return (
    <div className="soft-ink-wash" aria-hidden="true">
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-a" />
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-b" />
      <div className="soft-ink-wash-bloom soft-ink-wash-bloom-c" />
      <div className="soft-ink-wash-fiber" />
      <svg className="soft-ink-wash-mark" viewBox="0 0 640 360" preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="soft-ink-blot" cx="50%" cy="48%" r="55%">
            <stop offset="0%" stopColor="rgba(192,122,58,0.22)" />
            <stop offset="55%" stopColor="rgba(120,78,42,0.08)" />
            <stop offset="100%" stopColor="rgba(10,9,8,0)" />
          </radialGradient>
          <filter id="soft-ink-smudge" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.012 0.04"
              numOctaves="2"
              seed="7"
              result="noise"
            >
              <animate
                attributeName="baseFrequency"
                dur="28s"
                values="0.012 0.04;0.016 0.028;0.012 0.04"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="18" />
          </filter>
        </defs>
        <ellipse
          className="soft-ink-wash-blot"
          cx="420"
          cy="170"
          rx="210"
          ry="130"
          fill="url(#soft-ink-blot)"
          filter="url(#soft-ink-smudge)"
        />
        <path
          className="soft-ink-wash-stroke"
          d="M72 268 C 160 240, 250 300, 340 250 S 520 210, 590 248"
          fill="none"
          stroke="rgba(192,122,58,0.28)"
          strokeWidth="1.25"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
