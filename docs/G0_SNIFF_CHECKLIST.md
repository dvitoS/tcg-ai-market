# G0 Spot sniff pack (ops)

**Gate:** paid marketing stays locked until this pack passes.

**When:** after a green nightly (quotes + sure_rows).

## Automated path (preferred)

1. Sign in as an **ops** user on Soft Ink → **System status**.
2. Click **Pokreni auto G0** / **Run auto G0**.
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
   If not → Heal remaining fails / re-run after nightly. Do **not** unlock spend.

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
