# CAT.2 — TCGdex / Scrydex catalog cutover (prep)

**Why:** pokemontcg.io is deprecated; existing keys work until **2027-03-01**. Soft Ink still keys cards on pokemontcg ids (`sv1-1`). TCGdex uses different ids (`sv01-001`).

**Spend unlock:** CAT.2 does **not** block G0–G3 / M4.5. Art fallback (CAT.1) is enough until ads. Full remap can land in slices.

## ID shape

| Soft Ink (pokemontcg) | TCGdex |
| --- | --- |
| `sv1-1` | `sv01-001` |
| `sv3pt5-25` | `sv03.5-025` |
| `me1-4` | `me01-004` |
| `me55-27` | `30th-027` |
| `zsv10pt5-111` | `sv10.5b-111` |

Collector numbers usually align after zero-pad. Exceptions (do **not** blind-map): `me55c` Classic Collection, some promo lines.

## Phased ship

| Slice | Goal | Status |
| --- | --- | --- |
| **CAT.2a** | Expand Soft Ink → TCGdex **set map** for SV + ME; art URL remap / `onError` | **This PR** |
| **CAT.2b** | Nightly gap-fill can **read** TCGdex when pokemontcg fails (keep Soft Ink ids) | Later |
| **CAT.2c** | Optional Scrydex Growth if we need paid catalog+prices (CAT.3) | Optional |
| **CAT.2d** | Persist remap table in DB + dual-read before flipping primary source | Before EOL |

## Invariants

- Soft Ink `card_id` stays pokemontcg-shaped until CAT.2d.
- Art may come from `assets.tcgdex.net` without changing ids.
- Never invent maps for sets where localIds diverge.
- No API key required for TCGdex assets / public REST.

## Code

- Python: `tcgdex_client.py` (`_SET_MAP`, `pokemontcg_to_tcgdex_id`, `tcgdex_image_url`)
- Soft Ink: `web/src/lib/cardImage.ts` (keep maps in sync)
