# G0 Spot sniff pack (ops)

**Gate:** paid marketing stays locked until this pack passes.

**When:** after a green nightly (quotes + sure_rows). Last green: run `42505043442` (#158) — ~20k quotes, sure_rows ≥ 2.5k.

## Steps

1. Sign in as an **ops** user on Soft Ink → **System status**.
2. Open **Spot sniff pack (G0)** → Load sniff pack (default 20 = ~10 UNDER + ~10 OVER).
3. For each row:
   - Open **Kestrel** card detail (spot / sure fair band).
   - Open **TCGplayer** product link (NM market).
   - Check recent **eBay sold** comps (same printing / NM when possible).
4. Mark **pass** only if spot is plausible for NM and the sure UNDER/OVER side still makes sense.
5. **Any hard fail** → heal / quarantine via Data Health, re-run sniff after the next nightly (or spot heal). Do **not** unlock spend.

## Pass criteria

- ≥18/20 rows pass TCP + eBay sold smell-test (or 100% of a smaller pack if board is thin).
- Unmatched JustTCG set rate not spiking vs prior nightly.
- Methodology page live: `/guides/kestrel-methodology`.

## API (optional)

```http
GET /api/data-health/sniff-pack?limit=20
Authorization: Bearer <ops access token>
```
