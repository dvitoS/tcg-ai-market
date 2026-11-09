"""TCGdex id / art helpers — Soft Ink fallback while pokemontcg CDN lags."""

from tcgdex_client import (
    mapped_pokemontcg_set_codes,
    pad_local_id,
    pokemontcg_to_tcgdex_id,
    prefer_card_image_url,
    tcgdex_image_url,
)


def test_pad_local_id_digits_and_promo() -> None:
    assert pad_local_id("27", 3) == "027"
    assert pad_local_id("284", 3) == "284"
    assert pad_local_id("H29", 3) == "H29"
    assert pad_local_id("TG1", 3) == "TG1"


def test_pokemontcg_to_tcgdex_id_mapped_sets() -> None:
    assert pokemontcg_to_tcgdex_id("me55-27") == "30th-027"
    assert pokemontcg_to_tcgdex_id("me2pt5-284") == "me02.5-284"
    assert pokemontcg_to_tcgdex_id("zsv10pt5-111") == "sv10.5b-111"
    assert pokemontcg_to_tcgdex_id("rsv10pt5-156") == "sv10.5w-156"
    assert pokemontcg_to_tcgdex_id("sv1-1") == "sv01-001"
    assert pokemontcg_to_tcgdex_id("sv3pt5-25") == "sv03.5-025"
    assert pokemontcg_to_tcgdex_id("sv8pt5-1") == "sv08.5-001"
    assert pokemontcg_to_tcgdex_id("me3-4") == "me03-004"
    # Classic Collection numbering differs — no blind map.
    assert pokemontcg_to_tcgdex_id("me55c-4") is None
    assert pokemontcg_to_tcgdex_id("base1-4") is None


def test_mapped_set_codes_cover_sv_and_me() -> None:
    codes = set(mapped_pokemontcg_set_codes())
    assert "sv1" in codes and "sv10" in codes and "me1" in codes
    assert "me55c" not in codes


def test_tcgdex_image_url_high_webp() -> None:
    url = tcgdex_image_url("me55-27")
    assert url == "https://assets.tcgdex.net/en/me/30th/027/high.webp"
    url2 = tcgdex_image_url("me2pt5-284")
    assert url2 == "https://assets.tcgdex.net/en/me/me02.5/284/high.webp"
    assert tcgdex_image_url("sv1-1") == (
        "https://assets.tcgdex.net/en/sv/sv01/001/high.webp"
    )


def test_prefer_rewrites_broken_pokemontcg_cdn() -> None:
    broken = "https://images.pokemontcg.io/me55/27.png"
    out = prefer_card_image_url("me55-27", broken)
    assert out is not None
    assert "assets.tcgdex.net" in out
    assert out.endswith("/high.webp")


def test_prefer_keeps_good_existing_non_broken() -> None:
    good = "https://images.pokemontcg.io/sv10/239.png"
    assert prefer_card_image_url("sv10-239", good) == good


def test_prefer_fills_missing_for_mapped_set() -> None:
    out = prefer_card_image_url("me2pt5-284", None)
    assert out == "https://assets.tcgdex.net/en/me/me02.5/284/high.webp"
    assert prefer_card_image_url("sv3-25", None) == (
        "https://assets.tcgdex.net/en/sv/sv03/025/high.webp"
    )
