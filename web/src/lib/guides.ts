export type GuideSection = {
  heading: string;
  body: string[];
};

export type GuideFaq = {
  question: string;
  answer: string;
};

export type Guide = {
  slug: string;
  title: string;
  description: string;
  eyebrow: string;
  lede: string;
  sections: GuideSection[];
  faqs: GuideFaq[];
  primaryCta: { href: string; label: string };
  secondaryCta?: { href: string; label: string };
};

export const GUIDES: Guide[] = [
  {
    slug: "pokemon-tcg-fair-value",
    title: "Pokémon TCG fair value: spot vs a sure AI band",
    description:
      "How Kestrel Soft Ink scores Pokémon TCG fair value — spot price, sure AI fair band, and when a card looks underpriced or overpriced.",
    eyebrow: "Guide",
    lede:
      "Collectors and traders often ask “what is this card really worth?” Spot tells you the last market print. Fair value asks whether that print looks cheap or rich versus a model band you can trust.",
    sections: [
      {
        heading: "Spot is not the whole story",
        body: [
          "Spot (or market) price is the current board quote — useful, but noisy. A single printing, condition, or thin listing can move it without changing the card’s longer outlook.",
          "Kestrel Soft Ink reads spot next to an AI fair estimate and a conformal “sure” band. When confidence is weak, we stay quiet instead of forcing a buy or sell call.",
        ],
      },
      {
        heading: "What “sure fair band” means",
        body: [
          "The sure band is the range where the model is confident enough to speak. Inside it, we treat the deal as roughly fair on that horizon. Outside it — with confidence gates green — Soft Ink can label a single underpriced or overpriced.",
          "That is the wedge versus pure price trackers: not another chart, a clear call when the band and confidence agree.",
        ],
      },
      {
        heading: "How to use Deal of the Day and Radar",
        body: [
          "Deal of the Day surfaces a short list of underpriced picks on the public board. Kestrel Radar unlocks the full sure under/over desk with filters.",
          "Start from the call and the band, then check set, rarity, and liquidity before you buy. Fair value is a decision aid — not a guarantee.",
        ],
      },
    ],
    faqs: [
      {
        question: "Is Kestrel fair value the same as TCGplayer market?",
        answer:
          "No. Spot often tracks market quotes; fair value is Kestrel’s AI estimate plus a sure band. They can disagree — that disagreement is the signal.",
      },
      {
        question: "Why do some cards show HOLD or unsure?",
        answer:
          "When the band or confidence gate is weak, Soft Ink stays quiet. Silence beats a loud wrong call.",
      },
    ],
    primaryCta: { href: "/browse", label: "Browse the board →" },
    secondaryCta: { href: "/radar", label: "Open Kestrel Radar →" },
  },
  {
    slug: "should-i-grade",
    title: "Should I grade this Pokémon card?",
    description:
      "A practical guide to Pokémon TCG grading EV — raw spot, PSA/slab comps, fees, and when Kestrel Soft Ink says grade vs pass.",
    eyebrow: "Guide",
    lede:
      "Grading only pays when the slab premium clears fees, risk, and time. Soft Ink’s grading desk compares raw value to graded outcomes so you can decide grade vs hold vs sell raw.",
    sections: [
      {
        heading: "Start from raw economics",
        body: [
          "Write down raw spot, expected grade mix, slab comps, and all-in costs (submission, shipping, insurance). If the optimistic slab path barely clears fees, pass.",
          "Population and liquidity matter: a PSA 10 that never sells is not EV — it is inventory.",
        ],
      },
      {
        heading: "Where Soft Ink helps",
        body: [
          "On card detail, Soft Ink can show grading EV style framing against live board context. Use it with your own condition read — AI does not see whitening or centering the way your eyes do.",
          "If Radar already flags the raw as underpriced, selling raw can beat a slow grade. If raw looks fair but slabs print a wide premium, grading may be the better desk.",
        ],
      },
      {
        heading: "A simple decision rule",
        body: [
          "Grade when expected net after fees beats selling raw by a margin that covers time and breakage risk. Otherwise sell raw, or hold.",
          "Re-check comps the day you submit — graded markets move while cards sit in a queue.",
        ],
      },
    ],
    faqs: [
      {
        question: "Does Kestrel guarantee a PSA 10?",
        answer:
          "No. Soft Ink frames economics and board context. Grade outcome still depends on the physical card and the grader.",
      },
      {
        question: "Should every chase card be graded?",
        answer:
          "No. Many chase cards are more liquid raw. Grade when the slab premium is real and durable, not automatic.",
      },
    ],
    primaryCta: { href: "/browse", label: "Find a card to evaluate →" },
    secondaryCta: { href: "/pro", label: "See Kestrel Pro →" },
  },
  {
    slug: "trade-fairness",
    title: "Is this Pokémon TCG trade fair?",
    description:
      "How to judge Pokémon card trade fairness with spot totals and Kestrel AI fair value — fair, you-ahead, or them-ahead in Soft Ink Trade Analyzer.",
    eyebrow: "Guide",
    lede:
      "A trade can look even on sticker prices and still be lopsided on outlook. Soft Ink Trade Analyzer scores both sides on spot and AI fair so you see fair / you-ahead / them-ahead in plain language.",
    sections: [
      {
        heading: "Two ledgers: spot and fair",
        body: [
          "Spot totals answer “who brings more market value today?” Fair totals answer “who brings more model value on the sure band?” Soft Ink shows both.",
          "Within a small band (about ±3% by default), we call the trade fair. Outside it, the verdict names who is ahead.",
        ],
      },
      {
        heading: "Condition and printing matter",
        body: [
          "NM Normal is the AI board’s home base. Soft Ink applies condition and printing adjustments — and live variant spots when JustTCG can resolve them — so a LP holofoil does not pretend to be NM.",
          "Always match the physical cards you are handing across the table.",
        ],
      },
      {
        heading: "Share the call, not the vibe",
        body: [
          "After you score a trade, Soft Ink can copy a share link or export a report image for Discord or a local shop. That keeps the conversation on numbers, not vibes.",
          "Trade Analyzer is a Kestrel Pro surface — free desks still help you browse and learn the fair-band language first.",
        ],
      },
    ],
    faqs: [
      {
        question: "What does YOU_AHEAD mean?",
        answer:
          "From your seat, the side you receive is worth more than the side you give on the primary ledger Soft Ink prefers (AI fair when both sides match).",
      },
      {
        question: "Can a fair spot trade be a bad AI trade?",
        answer:
          "Yes. Spot can be even while fair totals lean one way — that is often the most useful Soft Ink signal.",
      },
    ],
    primaryCta: { href: "/trade", label: "Open Trade Analyzer →" },
    secondaryCta: { href: "/pro", label: "Unlock with Kestrel Pro →" },
  },
];

export function getGuide(slug: string): Guide | undefined {
  return GUIDES.find((g) => g.slug === slug);
}

export function guidePath(slug: string): string {
  return `/guides/${slug}`;
}
