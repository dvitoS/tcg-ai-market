"""EPN affiliate URL tagging."""

from __future__ import annotations

from services.epn import affiliate_ebay_url, epn_configured, sanitize_customid, tag_listing_urls


def test_sanitize_customid():
    assert sanitize_customid("detail/active sv3-1!") == "detail-active-sv3-1"


def test_affiliate_noop_without_campid(monkeypatch):
    import services.epn as epn

    monkeypatch.setattr(epn, "_clean", lambda name: "")
    url = "https://www.ebay.com/itm/123"
    assert affiliate_ebay_url(url) == url
    assert epn_configured() is False


def test_affiliate_tags_ebay_item(monkeypatch):
    import services.epn as epn

    def clean(name: str) -> str:
        return {
            "EPN_CAMPID": "5338123456",
            "EPN_MKRID": "711-53200-19255-0",
            "EPN_TOOLID": "10001",
        }.get(name, "")

    monkeypatch.setattr(epn, "_clean", clean)
    assert epn_configured() is True
    out = affiliate_ebay_url(
        "https://www.ebay.com/itm/123456789012",
        customid="detail-active-sv3-1",
    )
    assert "campid=5338123456" in out
    assert "mkcid=1" in out
    assert "mkevt=1" in out
    assert "customid=detail-active-sv3-1" in out
    assert "mkrid=711-53200-19255-0" in out


def test_affiliate_skips_non_ebay(monkeypatch):
    import services.epn as epn

    monkeypatch.setattr(
        epn,
        "_clean",
        lambda name: "5338123456" if name == "EPN_CAMPID" else "",
    )
    url = "https://example.com/item/1"
    assert affiliate_ebay_url(url) == url


def test_tag_listing_urls(monkeypatch):
    import services.epn as epn

    monkeypatch.setattr(
        epn,
        "_clean",
        lambda name: "5338123456" if name == "EPN_CAMPID" else "",
    )
    rows = [{"url": "https://www.ebay.com/itm/99", "title": "X"}]
    tagged = tag_listing_urls(rows, customid="scanner")
    assert "campid=5338123456" in tagged[0]["url"]
    assert rows[0]["url"] == "https://www.ebay.com/itm/99"
