"""TCGdex (https://tcgdex.dev) — free catalog/art helper.

No API key. Used as an image CDN fallback while Soft Ink still keys cards on
pokemontcg.io ids. Full catalog cutover stays a later roadmap item (EOL 2027).

Docs: https://tcgdex.dev/rest · Base: https://api.tcgdex.net/v2/en/
Images: https://assets.tcgdex.net/en/{serie}/{set}/{localId}/high.webp

When TCGdex lists a mapped set without uploaded art (e.g. Delta Reign / me6),
prefer the public Scrydex CDN: https://images.scrydex.com/pokemon/{id}/large
"""

from __future__ import annotations

from typing import NamedTuple

TCGDEX_ASSETS = "https://assets.tcgdex.net"
TCGDEX_API = "https://api.tcgdex.net/v2"
SCRYDEX_CDN = "https://images.scrydex.com"
POKEMONTCG_CDN_HOST = "images.pokemontcg.io"


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

# Soft Ink sets that should skip TCGdex art and use Scrydex CDN instead.
# - me6: TCGdex me06 lists cards but image=null (no CDN art yet)
# - me55c: Classic Collection — Soft Ink keeps original reprint numbers
#   (me55c-4 Charizard); TCGdex 30th-c uses 001–030 and also has no art yet.
# Do NOT blind-map me55c into _SET_MAP.
_TCGDEX_MISSING_ART_SETS = frozenset(
    {
        "me6",  # Delta Reign
        "me55c",  # 30th Celebration: Classic Collection
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


def scrydex_image_url(card_id: str, *, size: str = "large") -> str | None:
    """Build a Scrydex CDN URL (Soft Ink / pokemontcg id, no API key).

    Example: me6-1 → https://images.scrydex.com/pokemon/me6-1/large
    """
    cid = str(card_id or "").strip()
    if not cid or "-" not in cid:
        return None
    size_s = "small" if str(size or "").strip().lower() == "small" else "large"
    return f"{SCRYDEX_CDN}/pokemon/{cid}/{size_s}"


def is_pokemontcg_cdn_url(url: str | None) -> bool:
    text = str(url or "").strip().lower()
    return bool(text) and POKEMONTCG_CDN_HOST in text


def is_tcgdex_assets_url(url: str | None) -> bool:
    text = str(url or "").strip().lower()
    return bool(text) and "assets.tcgdex.net" in text


def is_scrydex_cdn_url(url: str | None) -> bool:
    text = str(url or "").strip().lower()
    return bool(text) and "images.scrydex.com" in text


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

    Exception: sets in `_TCGDEX_MISSING_ART_SETS` (e.g. Delta Reign / me6)
    use Scrydex CDN instead — TCGdex has catalog rows but no uploaded art.
    """
    existing_s = str(existing or "").strip() or None
    parts = split_card_id(card_id)
    set_code = parts[0] if parts else None

    tcgdex = tcgdex_image_url(card_id)
    scrydex = scrydex_image_url(card_id)
    broken_set = bool(
        set_code in _BROKEN_POKEMONTCG_CDN_SETS
        or pokemontcg_cdn_set_code(existing_s) in _BROKEN_POKEMONTCG_CDN_SETS
    )

    # Delta Reign etc.: skip dead TCGdex asset URLs → Scrydex.
    if set_code in _TCGDEX_MISSING_ART_SETS and scrydex:
        if is_scrydex_cdn_url(existing_s):
            return existing_s
        if (
            not existing_s
            or is_pokemontcg_cdn_url(existing_s)
            or is_tcgdex_assets_url(existing_s)
            or broken_set
        ):
            return scrydex
        return existing_s

    if tcgdex and (
        not existing_s
        or (broken_set and is_pokemontcg_cdn_url(existing_s))
        or (set_code in _SET_MAP and is_pokemontcg_cdn_url(existing_s) and broken_set)
    ):
        return tcgdex

    if existing_s:
        return existing_s
    return tcgdex or scrydex
