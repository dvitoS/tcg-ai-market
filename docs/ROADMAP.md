# Kestrel Soft Ink — Product Roadmap

**Positioning:** Collectr tracks *what you own*. PriceCharting shows *what sold*. TCGplayer is *where you buy*. **Kestrel** is the desk that answers *should I buy / sell / trade / grade — with conformal AI, not vibes*.

Last updated: 2026-11-05. Living doc — ship order can move; the wedge should not.

**North star for the next stretch:** make the wedge obvious in ~10 seconds for a non-Pro visitor (*fair / not fair — here’s why*), then earn Pro with shareable verdicts and trustworthy spots — **not** by becoming another binder scanner.

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
| 10 | Sealed product quotes | JustTCG / demo seed → `sealed:{id}` |

---

## Now — conversion & trust (ship order)

These close the loop we actually need before marketing spend. Do **not** reorder into Collectr features first.

### Phase A — Clarity + free teaser *(shipping)*

**Goal:** a visitor understands the desk without jargon; free users taste Pro without a full live board.

| ID | Item | Ship |
| --- | --- | --- |
| A1 | **Plain-language decision copy** | EN+HR glossary + one-liners (*“Selling ~15% under Kestrel’s fair band (sure).”*) on Radar rows, Deal of the Day, card detail; Trade fair-band note plain. |
| A2 | **Free teaser hardening** | Deal of the Day shows up to 5 UNDER picks, primary Pro CTA, same plain vocabulary as Radar. |
| A3 | **Landing “10-second wedge”** | Hero asks buy-or-pass; primary CTA scrolls to `#deal-of-day`; brand stays first. |

**Exit check:** cold visitor can explain what Kestrel does after one screen; free teaser loads fast and matches Pro vocabulary.

### Phase B — Shareable verdicts *(viral loop)*

**Goal:** Discord / local shops share a *fairness verdict*, not a spreadsheet.

| ID | Item | Ship |
| --- | --- | --- |
| B1 | **#8 Trade report PDF / image** — shipping | One-tap PNG export from `/trade` (+ public `/trade/s/{id}`): sides, fair totals, verdict, Kestrel watermark + Pro CTA. |
| B2 | **Binder share card (lite)** | Read-only visual summary of set completion (% / missing count / buy-cost) — **no** dealer margins or private P&L. Deep-link or image; Pro CTA optional. |
| B3 | **Radar share polish** — shipping | Keep `?share=`; clipboard includes plain-language blurb + filter URL. |

**Exit check:** someone can post a Trade or binder verdict in Discord without a Pro account to *view*; create/export stays Pro-gated where it already is.

### Phase C — Data trust *(stop lying spots)*

**Goal:** Radar / Trade / Grading EV sit on spots we trust enough to market.

| ID | Item | Ship |
| --- | --- | --- |
| C1 | **JustTCG set matching fix** | Kill bad resolves to `alternate-art-promos-pokemon` and similar; golden tests for set → JustTCG id. |
| C2 | **Spot / history QA panel** | Data health: % cards with fresh JustTCG history, unmatched sets, sure-row count after nightly. |
| C3 | **Nightly SLO** | Gap-fill catalog + drip JustTCG stays under timeout; board (`market_quotes`) refreshes every green run; cold Radar path stays usable (cache / warm if needed). |
| C4 | **Variant IDs (stretch)** | JustTCG printing/condition variants when matching is stable — replaces coarse NM multipliers where possible. |

**Exit check:** random Radar UNDER spots survive manual TCGplayer/eBay sniff test; unmatched-set rate tracked and trending down.

### Phase D — Reach only after Pro retention *(later)*

Ship these **after** A–C show Pro trial→paid and returning Radar/Trade use. Do not pull forward to “grow top of funnel.”

| ID | Item | Note |
| --- | --- | --- |
| D1 | PWA + installable Soft Ink | Bridge before native; home-screen + offline shell |
| D2 | Camera OCR scan | Photo ID → card → **same** fair/edge desk (OCR is input, not the product) |
| D3 | #5 Alert channels | Telegram / push (email + Discord already live) |
| D4 | Cardmarket / EU pricing | HR/EU dual-currency spots |
| D5 | Seller inventory sync | TCGplayer / CSV auto for dealer desk |
| D6 | Multi-TCG / JP lanes | Only with a data partner + proven Pokémon Pro retention |

---

## Explicit non-goals (for now)

- Full marketplace / checkout (deep-link eBay / TCGplayer)
- Sports cards
- **Becoming Collectr first** — binder scanner / album social without decision wedge
- **Casual Mode vs Investor Mode** dual UI — one desk, clearer copy instead
- **24–48h delayed AI freemium** — wrong lever; use capped live teaser instead
- Native app before PWA + proven OCR need

---

## Suggested next move

**Phase B1 + B3 shipping** — Trade report PNG + Radar share blurb.  
Next: **B2 binder share card (lite)**.  
Parallel ops: **Phase C1 JustTCG set matching**.
