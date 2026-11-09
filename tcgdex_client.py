"""TCGdex (https://tcgdex.dev) — free catalog/art helper.

No API key. Used as an image CDN fallback while Soft Ink still keys cards on
pokemontcg.io ids. Full catalog cutover stays a later roadmap item (EOL 2027).

CAT.2b: nightly gap-fill may **read** a mapped set from TCGdex when pokemontcg
fails, then rewrite rows back to Soft Ink ids (`sv1-1`).

Docs: https://tcgdex.dev/rest · Base: https://api.tcgdex.net/v2/en/
Images: https://assets.tcgdex.net/en/{serie}/{set}/{localId}/high.webp
"""

from __future__ import annotations

import logging
import re
from typing import Any, NamedTuple

import requests

TCGDEX_ASSETS = "https://assets.tcgdex.net"
TCGDEX_API = "https://api.tcgdex.net/v2"
POKEMONTCG_CDN_HOST = "images.pokemontcg.io"
LOG = logging.getLogger("kestrel.tcgdex")


class TcgdexSetMap(NamedTuple):
    """pokemontcg set id → TCGdex set + serie + localId zero-pad width."""

    set_id: str
    serie: str
    pad: int = 3


# Only map sets where collector numbers align with Soft Ink / pokemontcg ids.
# me55c Classic Collection uses a different numbering on TCGdex — skip blind map.
_SET_MAP: dict[str, TcgdexSetMap] = {
    # Mega Evolution era (Soft Ink meN → TCGdex me0N / specials)
    "me1": TcgdexSetMap("me01", "me", 3),
    "me2": TcgdexSetMap("me02", "me", 3),
    "me3": TcgdexSetMap("me03", "me", 3),
    "me4": TcgdexSetMap("me04", "me", 3),
    "me5": TcgdexSetMap("me05", "me", 3),
    "me6": TcgdexSetMap("me06", "me", 3),
    "me2pt5": TcgdexSetMap("me02.5", "me", 3),
    "me55": TcgdexSetMap("30th", "me", 3),
    # Scarlet & Violet main + trainer galleries / specials
    "sv1": TcgdexSetMap("sv01", "sv", 3),
    "sv2": TcgdexSetMap("sv02", "sv", 3),
    "sv3": TcgdexSetMap("sv03", "sv", 3),
    "sv3pt5": TcgdexSetMap("sv03.5", "sv", 3),
    "sv4": TcgdexSetMap("sv04", "sv", 3),
    "sv4pt5": TcgdexSetMap("sv04.5", "sv", 3),
    "sv5": TcgdexSetMap("sv05", "sv", 3),
    "sv6": TcgdexSetMap("sv06", "sv", 3),
    "sv6pt5": TcgdexSetMap("sv06.5", "sv", 3),
    "sv7": TcgdexSetMap("sv07", "sv", 3),
    "sv8": TcgdexSetMap("sv08", "sv", 3),
    "sv8pt5": TcgdexSetMap("sv08.5", "sv", 3),
    "sv9": TcgdexSetMap("sv09", "sv", 3),
    "sv10": TcgdexSetMap("sv10", "sv", 3),
    "zsv10pt5": TcgdexSetMap("sv10.5b", "sv", 3),
    "rsv10pt5": TcgdexSetMap("sv10.5w", "sv", 3),
}

# Sets where images.pokemontcg.io currently 404s for many/all cards.
_BROKEN_POKEMONTCG_CDN_SETS = frozenset(
    {
        "me55",
        "me55c",
        "me2pt5",
        "me1",
        "me2",
        "me3",
        "me4",
        "me5",
        "me6",
    }
)


def mapped_pokemontcg_set_codes() -> tuple[str, ...]:
    """Soft Ink set prefixes that have a TCGdex art/id remap."""
    return tuple(sorted(_SET_MAP))


def split_card_id(card_id: str) -> tuple[str, str] | None:
    text = str(card_id or "").strip()
    if "-" not in text:
        return None
    set_code, number = text.rsplit("-", 1)
    if not set_code or not number:
        return None
    return set_code, number


def pad_local_id(number: str, width: int = 3) -> str:
    """Pad numeric local ids (27 → 027); leave promo / letter ids alone (H29)."""
    raw = str(number or "").strip()
    if not raw:
        return raw
    if raw.isdigit():
        return raw.zfill(max(1, int(width)))
    return raw


def unpad_local_id(number: str) -> str:
    """Soft Ink / pokemontcg numbers drop leading zeros (001 → 1, TG01 → TG1)."""
    raw = str(number or "").strip()
    if not raw:
        return raw
    if raw.isdigit():
        return str(int(raw))
    match = re.match(r"^([A-Za-z]+)(\d+)$", raw)
    if match:
        return f"{match.group(1)}{int(match.group(2))}"
    return raw


def pokemontcg_set_to_tcgdex(set_code: str) -> TcgdexSetMap | None:
    return _SET_MAP.get(str(set_code or "").strip())


def tcgdex_local_to_pokemontcg_id(soft_set: str, local_id: str) -> str | None:
    """Build Soft Ink card id from a Soft Ink set code + TCGdex localId."""
    sid = str(soft_set or "").strip()
    local = unpad_local_id(local_id)
    if not sid or not local:
        return None
    return f"{sid}-{local}"


def pokemontcg_to_tcgdex_id(card_id: str) -> str | None:
    parts = split_card_id(card_id)
    if not parts:
        return None
    set_code, number = parts
    mapped = _SET_MAP.get(set_code)
    if mapped is None:
        return None
    return f"{mapped.set_id}-{pad_local_id(number, mapped.pad)}"


def tcgdex_image_url(
    card_id: str,
    *,
    lang: str = "en",
    quality: str = "high",
    ext: str = "webp",
) -> str | None:
    """Build a TCGdex assets URL from a Soft Ink / pokemontcg card id."""
    parts = split_card_id(card_id)
    if not parts:
        return None
    set_code, number = parts
    mapped = _SET_MAP.get(set_code)
    if mapped is None:
        return None
    local = pad_local_id(number, mapped.pad)
    q = str(quality or "high").strip() or "high"
    e = str(ext or "webp").strip().lstrip(".") or "webp"
    return (
        f"{TCGDEX_ASSETS}/{lang}/{mapped.serie}/{mapped.set_id}/{local}/{q}.{e}"
    )


def is_pokemontcg_cdn_url(url: str | None) -> bool:
    text = str(url or "").strip().lower()
    return bool(text) and POKEMONTCG_CDN_HOST in text


def pokemontcg_cdn_set_code(url: str | None) -> str | None:
    """Extract set code from https://images.pokemontcg.io/{set}/{number}.png."""
    text = str(url or "").strip()
    if not is_pokemontcg_cdn_url(text):
        return None
    try:
        # .../io/{set}/{number}.png
        path = text.split(POKEMONTCG_CDN_HOST, 1)[1]
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return parts[0]
    except Exception:
        return None
    return None


def prefer_card_image_url(card_id: str, existing: str | None = None) -> str | None:
    """Pick the best image URL for Soft Ink cards.

    Prefer TCGdex when the stored/synthesized URL points at a known-broken
    pokemontcg CDN set, or when we have no URL but a TCGdex map exists.
    """
    existing_s = str(existing or "").strip() or None
    parts = split_card_id(card_id)
    set_code = parts[0] if parts else None

    tcgdex = tcgdex_image_url(card_id)
    broken_set = bool(
        set_code in _BROKEN_POKEMONTCG_CDN_SETS
        or pokemontcg_cdn_set_code(existing_s) in _BROKEN_POKEMONTCG_CDN_SETS
    )

    if tcgdex and (
        not existing_s
        or (broken_set and is_pokemontcg_cdn_url(existing_s))
        or (set_code in _SET_MAP and is_pokemontcg_cdn_url(existing_s) and broken_set)
    ):
        return tcgdex

    if existing_s:
        return existing_s
    return tcgdex


_CATEGORY_TO_SUPERTYPE = {
    "Pokemon": "Pokémon",
    "Pokémon": "Pokémon",
    "Trainer": "Trainer",
    "Energy": "Energy",
}


def _tcgdex_get(path: str, *, timeout: float = 45.0) -> dict[str, Any] | list[Any]:
    url = f"{TCGDEX_API}/en/{path.lstrip('/')}"
    res = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, (dict, list)):
        raise RuntimeError(f"Unexpected TCGdex payload for {path}")
    return data


def tcgdex_set_card_rows_as_pokemontcg(
    soft_set_id: str,
    *,
    set_name: str | None = None,
    lang: str = "en",
) -> list[dict[str, Any]]:
    """Fetch one mapped set from TCGdex and emit pokemontcg-shaped card dicts.

    Soft Ink ``id`` stays ``{soft_set}-{unpadded localId}``. Used when
    pokemontcg.io gap-fill fails for a mapped set (CAT.2b).
    """
    soft = str(soft_set_id or "").strip()
    mapped = pokemontcg_set_to_tcgdex(soft)
    if mapped is None:
        return []

    payload = _tcgdex_get(f"sets/{mapped.set_id}")
    if not isinstance(payload, dict):
        return []
    label = (
        str(set_name or "").strip()
        or str(payload.get("name") or "").strip()
        or soft
    )
    rows_in = payload.get("cards") or []
    if not isinstance(rows_in, list):
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        local = str(row.get("localId") or "").strip()
        soft_id = tcgdex_local_to_pokemontcg_id(soft, local)
        if not soft_id or soft_id in seen:
            continue
        seen.add(soft_id)
        name = str(row.get("name") or "").strip() or None
        image_base = str(row.get("image") or "").strip().rstrip("/")
        # List endpoint image is a base path; Soft Ink prefers full file URLs.
        large = f"{image_base}/high.webp" if image_base else tcgdex_image_url(soft_id)
        small = f"{image_base}/low.webp" if image_base else large
        category = str(row.get("category") or "").strip()
        out.append(
            {
                "id": soft_id,
                "name": name,
                "supertype": _CATEGORY_TO_SUPERTYPE.get(category),
                "rarity": row.get("rarity"),
                "set": {"id": soft, "name": label},
                "images": {"small": small, "large": large},
                # Marker for ops / tests — not persisted by clean_cards.
                "_source": "tcgdex",
            }
        )
    LOG.info(
        "CAT.2b TCGdex fallback set=%s tcgdex=%s cards=%s",
        soft,
        mapped.set_id,
        len(out),
    )
    return out


def tcgdex_catalog_fallback_enabled() -> bool:
    """Default on — set NIGHTLY_TCGDEX_FALLBACK=0 to disable."""
    import os

    raw = str(os.environ.get("NIGHTLY_TCGDEX_FALLBACK", "1") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}
