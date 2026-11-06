"""Cardmarket deep-link helper (mirrored by web/src/lib/cardmarket.ts)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def cardmarket_search_url(name: str, set_name: str | None = None) -> str:
    from urllib.parse import urlencode

    q = " ".join(p for p in (str(name or "").strip(), str(set_name or "").strip()) if p)
    return "https://www.cardmarket.com/en/Pokemon/Products/Search?" + urlencode(
        {"searchString": q or name}
    )


def test_cardmarket_search_url_encodes_name_and_set() -> None:
    url = cardmarket_search_url("Pikachu", "Obsidian Flames")
    parsed = urlparse(url)
    assert parsed.netloc == "www.cardmarket.com"
    assert parsed.path.endswith("/Pokemon/Products/Search")
    qs = parse_qs(parsed.query)
    assert qs["searchString"] == ["Pikachu Obsidian Flames"]
