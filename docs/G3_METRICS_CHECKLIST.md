# G3 metrics gate (ops)

**Gate:** paid marketing stays locked until refund/cancel “wrong prices” stay under **2%**.

**When:** after G0 is green and soft-launch funnel is recording events.

## What Soft Ink tracks

| Signal | Where | Notes |
| --- | --- | --- |
| Trial → paid | Data Health → Trial → paid | `active` / `trialing` / `canceled` |
| Cancel / refund reasons | Data Health → **G3 trust gate** | Creem webhook reasons when present; **reason buckets** listed |
| Wrong-price cites | Same strip | Keyword match on cancel/refund reason (&lt;2% target) |
| Wrong-spot reports | Data Health → Wrong-spot reports + funnel `spot_report` | Soft proxy before refund volume exists |
| Spend unlock rollup | Data Health → **Spend unlock (G0–G3)** | G0 nightly + G3 gate + SLA + G2 share proxy |

Funnel **and G3 cancel/refund counters** persist across API restarts (local JSON + Supabase `model_artifacts` when available). Entitlement counts come from `pro_entitlements`.
`landing_view` / `dotd_view` / activate events fire **once per browser day** (not on every refresh).

## Pass criteria

1. Funnel events flowing (`landing_view` → Pro → Radar/Trade/Alerts → `share_*`).  
   `landing_cta_pro` fires from **header + locked-desk Pro links** (not the landing hero — T1.3 one-job). Locked-desk checkout fires `pro_checkout_click`.  
   Pro wedge: `pro_open_alerts` → Portfolio bootstrap fires `alerts_activate` (once/day).
2. Trial → paid strip readable (not empty source for days).
3. **Wrong-price cite % &lt; 2%** once you have cancel/refund reasons (`gate_ok` true).  
   If Creem sends no reason, keep volume of open wrong-spot reports low and resolve within SLA (`docs/WRONG_SPOT_SLA.md`).
4. No spike of refunds that ops manually tags as “wrong prices” in Discord/Creem notes.
5. Data Health **Spend unlock** card shows G0 green and G3 not blocked (G1 remains manual checklist).

## Manual Creem check

1. Creem dashboard → refunds / cancellations for the week.
2. If a customer cites bad spots/prices, note it — Soft Ink will bucket webhook reasons containing “wrong price / krivi spot / …” as `wrong_price`.
3. Re-open Data Health → G3 trust gate after the webhook lands.

## API

```http
GET /api/billing/conversion
Authorization: Bearer <ops access token>
```

Response includes:
- `g3_trust` — `wrong_price_pct`, `gate_ok`, spot-report rate, `reason_buckets`, `persisted` / `source`
- `spend_unlock` — G0–G3 rollup (`ready`, `blockers`, per-gate status)
