# Kestrel Soft Ink — Product Roadmap

**Positioning:** Collectr tracks *what you own*. PriceCharting shows *what sold*. TCGplayer is *where you buy*. **Kestrel** is the desk that answers *should I buy / sell / trade / grade — with conformal AI, not vibes*.

Last updated: 2026-11-08. Living doc — ship order can move; the wedge should not.

**North star:** make the wedge obvious in ~10 seconds for a non-Pro visitor (*fair / not fair — here’s why*), then earn Pro with shareable verdicts and trustworthy spots — **not** by becoming another binder scanner.

**Marketing spend unlock:** paid acquisition only after **G0–G3** below are green. Until then: organic soft launch only.

---

## Path to marketing spend ready (M0–M4)

Research basis (Nov 2026): r/PokemonTCG Collectr vs TCGplayer threads; r/PokemonInvesting “should I buy / is this a good trade?”; TCGinvest methodology + Collectr alternatives writeups; PriceCharting / seekTCG sold-comp guidance; Soft Ink desk audit.

### What Reddit already wants (and distrusts)

| Pattern | Implication for Kestrel |
| --- | --- |
| “Collectr for collection, TCP / eBay sold / PriceCharting for price” | **Price trust is the product.** Opaque or lagging spots = instant distrust. |
| Endless “Is this a good trade?” threads (Collectr trade analyzer screenshots) | **Shareable Trade verdict** is the viral loop — not news, not binder social. |
| “Should I buy this for $X?” / deal sniffing | Hero + DOTD + Radar UNDER is the exact job-to-be-done. |
| Collectr lag / inflated spikes complained about loudly | Marketing spend **amplifies** wrong spots. Sniff + heal before ads. |
| Investing-sub backlash against “it only goes up” vibes | Position as a **desk call with conformal certainty**, not financial advice / FOMO. |
| Sealed + graded debates | Sealed desk + Grading EV must be **correct and labeled** — not showcase filler. |

### Competitor map → Soft Ink response

| Player | Strength | Weakness | Kestrel move |
| --- | --- | --- | --- |
| **Collectr** | UX, scanner, portfolio, trade analyzer screenshots | Price lag / inflation; Reddit says don’t trust it for market | Do **not** out-Collectr. Beat on fair/trade verdict + trustworthy spot. |
| **TCGplayer** | Vendor pricing bible | No fair band / trade desk / AI call | Always deep-link; never contradict TCP silently. |
| **PriceCharting** | Closest to real solds; graded history | Not a buy/pass desk; US/eBay lens | Comps credibility; graded EV cites sold reality. |
| **TCGinvest** | Methodology page; US+EU side-by-side; sealed | Different wedge (momentum / portfolio analytics) | Copy **transparency + dual-source labeling**; skip news until a real feed. |
| **PokeTop10 / similar** | Movers + sealed heat | Momentum ≠ fair; narrow chase catalog | Pulse movers OK; **sure band** stays the decision. |

### Exit gates (must be green before paid spend)

| Gate | Status target | Exit check |
| --- | --- | --- |
| **G0 Trust** | Critical path | 20-card Radar sniff pack vs TCP + eBay sold passes; unmatched-set rate trending down; public `/guides` or methodology page live |
| **G1 10s wedge** | Mostly shipped | ≥4/5 cold users explain “spot vs sure fair band / buy or pass” after one screen |
| **G2 Share loop** | In progress | Trade / Radar / binder share viewable without Pro; ≥1 organic Discord share/week in soft launch |
| **G3 Metrics** | Required before CAC | Funnel instrumented; trial→paid path clear; &lt;2% refunds citing “wrong prices” |

### Phases

#### M0 — Price trust *(blocks everything)*

| ID | Item | Ship |
| --- | --- | --- |
| M0.1 | **Methodology page** | Public: JustTCG/TCP spot, eBay comps, conformal “sure” band, refresh cadence — TCGinvest transparency bar |
| M0.2 | **Spot sniff pack** | Ops: 20 random sure UNDER/OVER vs TCP + eBay sold; fail → **block marketing** |
| M0.3 | **JustTCG set matching** | No silent wrong-set joins; golden tests (= C1) |
| M0.4 | **Variant IDs** | Condition×printing when TCP resolves; else NM×multiplier **labeled** (= C4) |
| M0.5 | **Nightly SLO + board TTL** | Quotes-written gate; cold Radar usable (= C3) |
| M0.6 | **Poison / heal visibility** | Ops data-health; never ship known-poison as sure |

#### M1 — Decision clarity

| ID | Item | Ship |
| --- | --- | --- |
| M1.1 | Plain-language everywhere | Radar, DOTD, detail, Trade — one vocabulary (= A1) |
| M1.2 | Landing desk core | Hero slider → pulse → DOTD; no news / sealed clutter on first scroll |
| M1.3 | Free teaser quality | DOTD 5 UNDER = Pro vocabulary; fast SSR (= A2/A3) |
| M1.4 | Source labels on detail | Never blend US/EU; show source + as-of |
| M1.5 | Disclaimer tone | “Desk call, not financial advice” near AI band |

#### M2 — Viral verdicts

| ID | Item | Ship |
| --- | --- | --- |
| M2.1 | Trade report PNG | One-tap share + watermark + Pro CTA (= B1) |
| M2.2 | Radar share blurb | Clipboard plain-language + filter URL (= B3) |
| M2.3 | Binder share lite | % / owned / missing / buy-cost — no private P&L (= B2) |
| M2.4 | Deal-of-day share card | Daily UNDER pick image for Discord / IG |
| M2.5 | Reddit-ready deep links | `/trade/s/{id}` + card OG tags correct |

#### M3 — Desk depth that earns trust

| ID | Item | Ship |
| --- | --- | --- |
| M3.1 | Sealed desk correctness | Verified TCP art + live JustTCG; curated seed only if sniffed |
| M3.2 | Grading EV trust | Fees + gem-rate honesty; never imply 100% PSA 10 |
| M3.3 | eBay sold comps UX | Readable sold cluster next to fair band |
| M3.4 | Dealer CSV sync | Finish D5 for shops that price off TCP |
| M3.5 | Watchlist alerts quality | Sure-only default; no spam from poisoned spots |

#### M4 — Soft launch → spend unlock

| ID | Item | Ship |
| --- | --- | --- |
| M4.1 | Funnel events | landing → DOTD → Pro → Radar/Trade activation |
| M4.2 | Organic first | Discord / LGS / soft Reddit with share cards — **not** ads |
| M4.3 | Trial hygiene | Creem trial → paid conversion dashboard |
| M4.4 | Support playbook | Wrong-spot report → ops heal SLA |
| M4.5 | **Spend unlock** | G0–G3 green → tiny paid search / creator tests |

### Suggested next 3

1. **M0.1 + M0.2** — methodology page + 20-card sniff pack  
2. **M0.3–M0.5** — finish set matching, variant IDs, nightly SLO  
3. **M2.1** — Trade PNG (own “is this a good trade?”)

### Explicit non-goals until spend unlock

- News grid (“This week in Pokémon”) before a real feed + desk CTA  
- Becoming Collectr (binder social / multi-TCG catalog first)  
- Marketplace / checkout  
- Multi-TCG / JP without a data partner  
- **Paid ads before G0 sniff pack passes**

---

## Already shipped (baseline)

| Surface | What it does |
| --- | --- |
| Soft Ink cutover | Next.js + FastAPI; Streamlit retired |
| Browse / Signals | Catalog, AI ROI, conformal gates, art-first cards |
| Card detail | Multi-source chart, eBay comps, 7d AI outlook, Grading EV, Trade deep-links |
| Portfolio + watchlist | Lots, alerts (banner + email + Discord), filters |
| Scanner | Opportunity scan over catalog |
| **Kestrel Radar** `/radar` | Conformal UNDER/OVER mispricing desk (Kestrel Pro gate) |
| **Trade Analyzer** `/trade` | Two-sided fair / you-ahead / them-ahead |
| Dealer desk | CSV import/export, pro tools |
| Kestrel Pro | Creem billing, entitlements, `/pro` teaser radar |
| Search suggest | Recent + catalog typeahead (portaled overlay) |
| i18n | EN + HR |
| Ops | Data health panel, deploy docs, nightly train / quotes + catalog gap-fill |
| Landing desk core | Hero sure-under slider + Market Pulse + Deal of the Day |
| Soft Ink chrome | Global copper thin scrollbars, art-first browse |

### Shipped from earlier “next 3” / Pro depth

| # | Item | Notes |
| --- | --- | --- |
| 1 | Shareable Trade & Radar links | `/trade/s/{id}` + Radar `?share=` |
| 2 | Portfolio equity curve + AI overlay | MTM + fair line + conformal TRIM callouts |
| 3 | Condition & printing on lots | Fixed NM multipliers; JustTCG variant IDs still deferred |
| 4 | Deal of the Day public feed | Landing + `/pro` reuse `/api/radar/preview` |
| 6 | Model trust panel | Retrain calibration, conformal coverage, hit rate |
| 7 | Grading EV v2 | PSA 9 + fees + break-even chart |
| 9 | Set completion / binder checklist | Soft Ink `/binder` |
| 10 | Sealed product quotes | JustTCG / demo seed → `sealed:{id}` (seed TCP ids verified 2026-11-08) |

---

## Legacy phase tags (A–D) — still tracked under M*

### Phase A — Clarity + free teaser → **M1**

| ID | Item | Ship |
| --- | --- | --- |
| A1 | Plain-language decision copy | → M1.1 |
| A2 | Free teaser hardening | → M1.3 |
| A3 | Landing “10-second wedge” | → M1.2 (hero slider + pulse + DOTD shipped) |

### Phase B — Shareable verdicts → **M2**

| ID | Item | Ship |
| --- | --- | --- |
| B1 | Trade report PNG / image | → M2.1 |
| B2 | Binder share card (lite) | → M2.3 |
| B3 | Radar share polish | → M2.2 |

### Phase C — Data trust → **M0**

| ID | Item | Ship |
| --- | --- | --- |
| C1 | JustTCG set matching fix | → M0.3 |
| C2 | Spot / history QA panel | Ops + → M0.6 |
| C3 | Nightly SLO | → M0.5 |
| C4 | Variant IDs | → M0.4 |

### Phase D — Reach

| ID | Item | Note |
| --- | --- | --- |
| D1 | PWA + installable Soft Ink | **Done** |
| D2 | Camera OCR scan | **Done** |
| D3 | Alert channels | Telegram skipped; push deferred. Email + Discord live |
| D4 | Cardmarket / EU pricing | **Done** — keep labeled, never blended (M1.4) |
| D5 | Seller inventory sync | → M3.4 |
| D6 | Multi-TCG / JP lanes | Only with data partner + proven Pokémon Pro retention |

---

## Explicit non-goals (for now)

- Full marketplace / checkout (deep-link eBay / TCGplayer)
- Sports cards
- **Becoming Collectr first** — binder scanner / album social without decision wedge
- **Casual Mode vs Investor Mode** dual UI — one desk, clearer copy instead
- **24–48h delayed AI freemium** — wrong lever; use capped live teaser instead
- Native app before PWA + proven OCR need
- Telegram alert channel (skipped; revisit with push later)
- Landing news / auction “record sales” until a real Soft Ink feed exists
