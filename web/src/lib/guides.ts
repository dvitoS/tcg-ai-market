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
    slug: "kestrel-methodology",
    title: "Kestrel methodology: where every number comes from",
    description:
      "How Kestrel builds Pokémon asking prices, a good price, deal calls, and why we refuse to blend opaque prices.",
    eyebrow: "Methodology",
    lede:
      "Collectors trust TCGplayer and eBay sold comps — not mysterious app prices. This page says exactly where Kestrel’s numbers come from, how often they refresh, and what a clear maybe-buy / maybe-skip lean means before you act.",
    sections: [
      {
        heading: "Asking price",
        body: [
          "Asking price is the Near Mint quote we attach to a catalog card — primarily TCGplayer-linked US seller quotes. When a live pull is unavailable, we fall back to the last saved quote rather than inventing a number.",
          "US and EU views stay labeled. We do not blend Cardmarket EUR into a fake USD “average.” If sources disagree beyond FX noise, treat that as a warning — not a single blended truth.",
        ],
      },
      {
        heading: "Good price + good-price range",
        body: [
          "A nightly training run fits a price model on history and writes a good-price estimate plus a range — the band where the model is allowed to speak.",
          "A clear call means confidence gates are green. Then deals can say looks cheap (maybe buy) or looks expensive (maybe skip). When gates fail, Kestrel stays quiet instead of forcing a tip.",
        ],
      },
      {
        heading: "Deals, Deal of the Day, and Trade",
        body: [
          "Deal of the Day and the public deals preview show capped “looks cheap” picks. Full deals adds filters and the full cheap / expensive list.",
          "Trade check scores both sides on asking and good price so you see fair / you’re ahead / they’re ahead — the same vocabulary as the buy/skip desk, not a sticker-sum alone.",
        ],
      },
      {
        heading: "Comps, grading, and sealed",
        body: [
          "Card detail can surface eBay sold comps next to the board. Sold clusters are the industry check against ask-price noise — use them before you trust a thin print.",
          "Grading EV frames fees and slab paths; it never guarantees a PSA 10. Sealed quotes use verified product ids — showcase art must match the named product.",
        ],
      },
      {
        heading: "Refresh cadence and human checks",
        body: [
          "Catalog updates, history, model retrain, and quote saves run on a nightly schedule. Live detail pulls may refresh prices within API quota limits.",
          "We also sample clear deal calls by hand against TCGplayer and eBay sold. A hard fail blocks paid marketing — price trust is the product.",
        ],
      },
    ],
    faqs: [
      {
        question: "Is Kestrel a replacement for TCGplayer?",
        answer:
          "No. TCGplayer remains the market standard for asks. Kestrel answers whether that asking price looks cheap or expensive versus a good price — then deep-links you back to marketplaces.",
      },
      {
        question: "Why do some cards have no deal call?",
        answer:
          "Weak history, weak confidence, or quarantined prices. Silence is intentional — better than a loud wrong tip.",
      },
      {
        question: "Do you blend US and EU prices?",
        answer:
          "No. Sources stay labeled. EUR views use FX conversion for display where configured; they are not averaged into a secret “true” price.",
      },
    ],
    primaryCta: { href: "/browse", label: "Browse cards →" },
    secondaryCta: { href: "/radar", label: "See deals →" },
  },
  {
    slug: "pokemon-tcg-fair-value",
    title: "Pokémon good price: asking vs a pretty-sure range",
    description:
      "How Kestrel scores a good price — asking price, pretty-sure range, and when a card looks cheap or expensive.",
    eyebrow: "Guide",
    lede:
      "Collectors and traders often ask “what is this card really worth?” Asking price tells you what sellers want. Good price asks whether that print looks cheap or expensive versus a range you can trust.",
    sections: [
      {
        heading: "Asking price is not the whole story",
        body: [
          "Asking (or market) price is the current seller quote — useful, but noisy. A single printing, condition, or thin listing can move it without changing the card’s longer outlook.",
          "Kestrel reads asking next to a good-price estimate and a pretty-sure range. When confidence is weak, we stay quiet instead of forcing a buy or sell call.",
        ],
      },
      {
        heading: "What “good-price range” means",
        body: [
          "The good-price range is where the model is confident enough to speak. Inside it, we treat the deal as roughly fair on that horizon. Outside it — with confidence gates green — Kestrel can label looks cheap or looks expensive.",
          "That is the wedge versus pure price trackers: not another chart, a clear call when the range and confidence agree.",
        ],
      },
      {
        heading: "How to use Deal of the Day and deals",
        body: [
          "Deal of the Day surfaces a short list of “looks cheap” picks on the public board. Full deals unlocks the pretty-sure cheap/expensive list with filters.",
          "Start from the call and the range, then check set, rarity, and liquidity before you buy. Good price is a decision aid — not a guarantee.",
        ],
      },
    ],
    faqs: [
      {
        question: "Is Kestrel’s good price the same as TCGplayer market?",
        answer:
          "No. Asking often tracks market quotes; good price is Kestrel’s estimate plus a pretty-sure range. They can disagree — that disagreement is the signal.",
      },
      {
        question: "Why do some cards show HOLD or unsure?",
        answer:
          "When the range or confidence gate is weak, Kestrel stays quiet. Silence beats a loud wrong call.",
      },
    ],
    primaryCta: { href: "/browse", label: "Browse cards →" },
    secondaryCta: { href: "/radar", label: "See deals →" },
  },
  {
    slug: "should-i-grade",
    title: "Should I grade this Pokémon card?",
    description:
      "A practical guide to Pokémon grading EV — raw asking price, PSA/slab comps, fees, and when Kestrel says grade vs skip.",
    eyebrow: "Guide",
    lede:
      "Grading only pays when the slab premium clears fees, risk, and time. Kestrel’s grading desk compares raw value to graded outcomes so you can decide grade vs hold vs sell raw.",
    sections: [
      {
        heading: "Start from raw economics",
        body: [
          "Write down raw asking price, expected grade mix, slab comps, and all-in costs (submission, shipping, insurance). If the optimistic slab path barely clears fees, skip.",
          "Population and liquidity matter: a PSA 10 that never sells is not EV — it is inventory.",
        ],
      },
      {
        heading: "Where Kestrel helps",
        body: [
          "On card detail, Kestrel can show grading EV style framing against live board context. Use it with your own condition read — AI does not see whitening or centering the way your eyes do.",
          "If deals already flag the raw as looks cheap, selling raw can beat a slow grade. If raw looks near good price but slabs print a wide premium, grading may be the better move.",
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
          "No. Kestrel frames economics and board context. Grade outcome still depends on the physical card and the grader.",
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
    title: "Is this Pokémon trade fair?",
    description:
      "How to judge Pokémon card trade fairness with asking totals and Kestrel good price — fair, you’re ahead, or they’re ahead.",
    eyebrow: "Guide",
    lede:
      "A trade can look even on sticker prices and still be lopsided on outlook. Kestrel trade check scores both sides on asking and good price so you see fair / you’re ahead / they’re ahead in plain language.",
    sections: [
      {
        heading: "Two ledgers: asking and good price",
        body: [
          "Asking totals answer “who brings more seller value today?” Good-price totals answer “who brings more model value on the pretty-sure range?” Kestrel shows both.",
          "Within a small band (about ±3% by default), we call the trade fair. Outside it, the verdict names who is ahead.",
        ],
      },
      {
        heading: "Condition and printing matter",
        body: [
          "NM Normal is the board’s home base. Kestrel applies condition and printing adjustments — and live variant asks when JustTCG can resolve them — so a LP holofoil does not pretend to be NM.",
          "Always match the physical cards you are handing across the table.",
        ],
      },
      {
        heading: "Share the call, not the vibe",
        body: [
          "After you score a trade, Kestrel can copy a share link or export a report image for Discord or a local shop. That keeps the conversation on numbers, not vibes.",
          "Trade check is a Kestrel Pro surface — free desks still help you browse and learn the asking / good-price language first.",
        ],
      },
    ],
    faqs: [
      {
        question: "What does YOU_AHEAD mean?",
        answer:
          "From your seat, the side you receive is worth more than the side you give on the primary ledger Kestrel prefers (good price when both sides match).",
      },
      {
        question: "Can a fair asking trade be a bad good-price trade?",
        answer:
          "Yes. Asking can be even while good-price totals lean one way — that is often the most useful Kestrel signal.",
      },
    ],
    primaryCta: { href: "/trade", label: "Open trade check →" },
    secondaryCta: { href: "/pro", label: "Unlock with Kestrel Pro →" },
  },
];

export function getGuide(slug: string): Guide | undefined {
  return GUIDES.find((g) => g.slug === slug);
}

export function guidePath(slug: string): string {
  return `/guides/${slug}`;
}
