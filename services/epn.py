"""eBay Partner Network (EPN) click-out tagging.

Adds campid / mkcid / mkevt tracking params to eBay item URLs.
No-op when ``EPN_CAMPID`` is unset.
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import _secret

# eBay US rotation (default). Override with EPN_MKRID for other marketplaces.
DEFAULT_MKRID = "711-53200-19255-0"
DEFAULT_TOOLID = "10001"
_CUSTOM_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def epn_campid() -> str:
    return _clean("EPN_CAMPID")


def epn_configured() -> bool:
    camp = epn_campid()
    return camp.isdigit() and len(camp) >= 6


def sanitize_customid(raw: str | None, *, max_len: int = 64) -> str:
    text = _CUSTOM_RE.sub("-", str(raw or "").strip())[:max_len].strip("-")
    return text


def _is_ebay_host(host: str) -> bool:
    h = (host or "").lower()
    return (
        h.endswith("ebay.com")
        or h.endswith("ebay.co.uk")
        or h.endswith("ebay.ca")
        or h.endswith("ebay.com.au")
        or h.endswith("ebay.de")
        or h.endswith("ebay.fr")
        or h.endswith("ebay.it")
        or h.endswith("ebay.es")
        or h == "ebay.us"
        or h.endswith(".ebay.us")
        or "ebay.com" in h
    )


def affiliate_ebay_url(
    url: str,
    *,
    customid: str | None = None,
) -> str:
    """Return URL with EPN params when configured; otherwise unchanged."""
    text = str(url or "").strip()
    if not text or not epn_configured():
        return text
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"}:
        return text
    if not _is_ebay_host(parts.netloc):
        return text

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["mkcid"] = "1"
    query["mkevt"] = "1"
    query["mkrid"] = _clean("EPN_MKRID") or DEFAULT_MKRID
    query["campid"] = epn_campid()
    query["toolid"] = _clean("EPN_TOOLID") or DEFAULT_TOOLID
    cid = sanitize_customid(customid) or sanitize_customid(_clean("EPN_CUSTOMID"))
    if cid:
        query["customid"] = cid
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def tag_listing_urls(
    rows: list[dict],
    *,
    customid: str | None = None,
) -> list[dict]:
    """Copy rows with ``url`` rewritten through EPN when configured."""
    if not rows or not epn_configured():
        return rows
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["url"] = affiliate_ebay_url(str(item.get("url") or ""), customid=customid)
        out.append(item)
    return out
