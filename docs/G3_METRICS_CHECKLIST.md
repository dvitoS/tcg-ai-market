# G3 metrics gate (ops)

**Gate:** paid marketing stays locked until refund/cancel “wrong prices” stay under **2%**.

**When:** after G0 is green and soft-launch funnel is recording events.

## What Soft Ink tracks

| Signal | Where | Notes |
| --- | --- | --- |
| Trial → paid | Data Health → Trial → paid | `active` / `trialing` / `canceled` |
| Cancel / refund reasons | Data Health → **G3 trust gate** | Creem webhook reasons when present |
| Wrong-price cites | Same strip | Keyword match on cancel/refund reason (&lt;2% target) |
| Wrong-spot reports | Data Health → Wrong-spot reports + funnel `spot_report` | Soft proxy before refund volume exists |

Process-local counters reset on API restart (soft launch). Entitlement counts come from `pro_entitlements`.

## Pass criteria

1. Funnel events flowing (`landing_view` → Pro → Radar/Trade → `share_*`).
2. Trial → paid strip readable (not empty source for days).
3. **Wrong-price cite % &lt; 2%** once you have cancel/refund reasons (`gate_ok` true).  
   If Creem sends no reason, keep volume of open wrong-spot reports low and resolve within SLA (`docs/WRONG_SPOT_SLA.md`).
4. No spike of refunds that ops manually tags as “wrong prices” in Discord/Creem notes.

## Manual Creem check

1. Creem dashboard → refunds / cancellations for the week.
2. If a customer cites bad spots/prices, note it — Soft Ink will bucket webhook reasons containing “wrong price / krivi spot / …” as `wrong_price`.
3. Re-open Data Health → G3 trust gate after the webhook lands.

## API

```http
GET /api/billing/conversion
Authorization: Bearer <ops access token>
```

Response includes `g3_trust` (`wrong_price_pct`, `gate_ok`, spot-report rate, reason buckets).
