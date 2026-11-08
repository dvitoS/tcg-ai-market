# Wrong-spot report → ops heal SLA (M4.4)

**Goal:** when a visitor says “this spot is wrong,” Kestrel acknowledges fast and tries a heal before ads amplify the lie.

## Intake

- Soft Ink card detail → **Report wrong spot** → `POST /api/spots/report`
- Process-local queue (resets on API restart) — soft launch only
- Funnel event: `spot_report`

## SLA

| Step | Target | Tooling |
| --- | --- | --- |
| Ack | ≤ **24h** | Ops marks report `acked` (`POST /api/spots/reports/{id}/status`) |
| Heal attempt | ≤ **48h** | Data Health heal buttons, or `POST /api/spots/reports/heal-open?mode=refetch` |
| Close | after verify | Status `resolved` (heal-open auto-resolves matched ids) / `dismissed` if false positive |

Overdue counts appear in Data Health → **Wrong-spot reports**.

## Playbook

1. Open Data Health → Wrong-spot reports (open + overdue).
2. Open the card on Kestrel + TCGplayer / eBay sold.
3. If poison-cluster / absurd tip: dry-run heal → `null_market` / `refetch`.
4. If isolated bad match: null market for that id, then refetch; leave Radar HOLD until sure again.
5. Reply in Discord/LGS only if the reporter is known — otherwise just heal silently.
6. Mark resolved; re-run sniff pack if UNDER/OVER board moved.

## Non-goals

- Public ticket portal / email replies
- Auto-posting user notes to Discord
- Guaranteeing a corrected JustTCG tip within 48h when the upstream feed is stuck
