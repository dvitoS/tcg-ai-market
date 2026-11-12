# Organic soft launch — Discord / LGS / soft Reddit

**Goal (G2):** ≥1 organic share per week using Kestrel share cards — **not** ads.
Paid spend stays locked until G0–G3 are green (`docs/ROADMAP.md`).

## Which card when

| Situation | Surface | What to post |
| --- | --- | --- |
| “Is this trade fair?” | **Trade** PNG + Discord paste | Verdict blurb + `/trade/s/{id}` |
| “What’s under today?” | **DOTD** PNG + paste | Featured UNDER + card deep link |
| “Show my board filters” | **Radar** PNG + paste (`?share=`) | Board totals + top UNDER + filter URL (Discord/Reddit OG unfurl) |
| “How close is this set?” | **Binder** PNG + paste (`?set=`) | Completion % / missing / buy-cost (Discord/Reddit OG unfurl) |

Always keep the desk disclaimer: *spot vs sure fair band — not financial advice.*

## Paste templates

### Discord (server / LGS channel)

```
Kestrel desk call — {one-line verdict}.
{spot / fair / edge line}
Desk call — spot vs sure fair band. Not financial advice.
{share URL}
```

Attach the PNG when you exported one (Trade / DOTD / Binder / Radar). Prefer the in-app **Copy Discord paste** / share buttons — they already assemble this pack.

### LGS counter talk (30 seconds)

1. Open the shared Trade or DOTD link on your phone.
2. Point at **spot vs sure fair** (not “the AI said buy”).
3. Offer the PNG in the shop Discord / WhatsApp if they want to revisit.

### Soft Reddit (TCG trade / local shops)

- Title: the verdict, not the brand (“Even trade on these 4 — fair band check”).
- Body: paste pack + one sentence that prices refresh live on the link.
- No affiliate spam; deep-link only. Avoid paid promo flair.

## Measurement

Funnel events (Data Health → Soft-launch funnel; persisted across API restarts):

- `share_copy` — clipboard paste pack (`surface`: trade / radar / dotd / binder)
- `share_png` — image export (`surface` + clipboard success)

G2 weekly check: at least one real human post outside the team, not just event counts.
Ops playbook + fastest first post: `docs/G2_SHARE_CHECKLIST.md`.

## Explicit non-goals

- Meta / TikTok / X ads
- Auto-posting bots into public Discords
- Soft Ink branding in user-facing copy (product is **Kestrel**)
