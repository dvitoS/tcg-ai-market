# Kestrel Soft Ink — Product Roadmap

**Positioning:** Collectr tracks *what you own*. PriceCharting shows *what sold*. TCGplayer is *where you buy*. **Kestrel** is the desk that answers *should I buy / sell / trade / grade — with conformal AI, not vibes*.

Last updated: 2026-11-05. Living doc — ship order can move; the wedge should not.

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
| Ops | Data health panel, deploy docs, nightly train / quotes |

---

## Now — next 3 (ship order)

These close conversion loops and plug the biggest holes vs Collectr / PriceCharting without diluting the AI wedge.

### 1. Shareable Trade & Radar links — Trade shipped
**Why:** Viral loop. Collectr/TCGplayer share collections; nobody shares a *fairness verdict* for a proposed trade.
**Ship:** ~~Public read-only `/trade/s/{id}`~~ (signed payload, live re-score, Kestrel Pro CTA). Radar `?share=…` still open.
**Pro gate:** Create share = Kestrel Pro (same as score); view = public.

### 2. Portfolio equity curve + AI overlay — shipped
**Why:** Collectr’s stock-chart is the retention hook we still lack.
**Ship:** ~~Daily MTM from `price_history`~~ (already live) + ~~today’s AI fair reference line~~ + ~~drawdown callouts with conformal TRIM count~~. Historical AI series still deferred (no quote snapshots).

### 3. Condition & printing on lots — shipped
**Why:** TCGplayer prices are condition/printing-specific; our spots are mostly raw-NM. Wrong condition = wrong Radar / Trade / Grading EV.
**Ship:** ~~`printing` on lots~~ + ~~fixed NM multipliers (LP/MP/HP/DMG × Normal/Reverse/Holo)~~ applied in portfolio MTM, equity curve, Trade lines, and Grading EV. JustTCG variant IDs still deferred.

---

## Next — Kestrel Pro depth

| # | Item | Competitive note |
| --- | --- | --- |
| 4 | **Deal of the Day** public feed — shipped | Landing + `/pro` reuse `/api/radar/preview` |
| 5 | **Alert channels** (Telegram / push / WhatsApp Business) | Deferred — email + Discord for now |
| 6 | **Model trust panel** — shipped | Kestrel Pro on `/radar`: retrain calibration, conformal coverage, Radar-call hit rate |
| 7 | **Grading EV v2** | PSA 9/10 pops, fee presets by service, break-even sensitivity chart |
| 8 | **Trade report PDF / image** | One-tap share for Discord groups / local shops |
| 9 | **Set completion / binder checklist** | Dex/Collectr hygiene — % complete, missing list, buy-cost to finish |
| 10 | **Sealed product quotes** | ETBs / boxes — Collectr’s other half of portfolio value |

---

## Later — market expansion

| # | Item | Note |
| --- | --- | --- |
| 11 | Real camera OCR scan | Today’s Scanner is catalog search; photo ID is table-stakes on mobile |
| 12 | Cardmarket / EU pricing | HR/EU users; dual-currency spots |
| 13 | Japanese / Asian print lanes | Cardbase / Dex territory — only if data partner exists |
| 14 | Multi-TCG (One Piece, Lorcana) | After Pokémon Pro retention is proven |
| 15 | PWA + installable Soft Ink | Bridge until native |
| 16 | Seller inventory sync (TCGplayer / CSV auto) | Dealer desk automation |
| 17 | Social / shared watchlists | Nice-to-have; not the wedge |

---

## Explicit non-goals (for now)

- Full marketplace / checkout (we deep-link to eBay / TCGplayer)
- Sports cards
- Replacing Collectr as a binder scanner first — we win on **decision quality**, then catch up on collection hygiene

---

## Suggested next move

**#5 Alert channels (Telegram / push)** — beyond email + Discord for Kestrel Pro retention.
