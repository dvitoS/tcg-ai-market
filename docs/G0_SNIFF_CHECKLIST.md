# G0 Spot sniff pack (ops)

**Gate:** paid marketing stays locked until this pack passes.

**Status:** **Green** as of 2026-11-12 — ops reports sniff pack good **3 nights in a row** (`g0_ready`). Keep nightly auto G0 on; re-open the gate if a nightly fails or fail count spikes.

**When:** after a green nightly (quotes + sure_rows). Nightly already runs auto G0 — manual click is only for leftovers / mid-day checks.

## Nightly (default — no ops click)

After post-retrain desk sweep + UNDER verify, `nightly_update` calls `run_nightly_auto_g0`:

- live JustTCG NM sniff on ~20 sure UNDER/OVER rows
- eBay sold only when `EBAY_SOLD_ENABLED=1` + Insights
- auto-heal hard fails
- writes `g0_ready` + `nightly_auto_g0` onto the spot_qa snapshot

Env: `NIGHTLY_AUTO_G0=1` (default), `NIGHTLY_AUTO_G0_LIMIT=20`, `NIGHTLY_G0_REQUIRED=0` (set `1` only when you want a non-ready pack to fail the job).

## Manual path (System status)

1. Sign in as an **ops** user on Soft Ink → **System status**.
2. Click **Pokreni auto G0** / **Run auto G0** if nightly left review rows or you need a mid-day recheck.
3. Soft Ink will:
   - sample ~20 sure UNDER/OVER rows
   - **resolve missing TCGplayer ids** via JustTCG search (common on older board rows)
   - batch-check **JustTCG NM** (TCP market)
   - parallel-check **eBay sold** medians only when `EBAY_SOLD_ENABLED=1` + Insights; otherwise TCP-only (no active-Browse proxy)
   - **auto-heal** hard fails (quarantine off the sure desk)
4. Read the summary: `pass · review · fail · healed`, TCP missing/resolved, and whether **G0 auto-ready**.
5. Open only the **review** rows (TCP + eBay links) — usually a handful, not all 20.  
   If you still see **20 review / 0 pass** and “no TCGplayer id”, JustTCG key is missing on the API or search couldn’t match — fix that before manual clicking.
6. If review rows smell OK and `g0_ready` is true → **G0 passes**.  
   If not → Heal remaining fails / wait for next nightly. Do **not** unlock spend.

## Pass criteria

- Auto (or manual) ≥18/20 pass after heals (or 100% of a thinner pack).
- Remaining **fail** count = 0.
- Unmatched JustTCG set rate not spiking vs prior nightly.
- Methodology page live: `/guides/kestrel-methodology`.

## API

```http
GET /api/data-health/sniff-pack?limit=20&live_check=true&ebay_check=true&auto_heal=true
Authorization: Bearer <ops access token>
```

`auto_heal=false` keeps hard fails in the list without quarantining.
