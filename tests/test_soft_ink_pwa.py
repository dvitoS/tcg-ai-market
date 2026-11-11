"""Soft Ink PWA shell — manifest + service worker + icons."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_PUBLIC = ROOT / "web" / "public"


def test_manifest_webmanifest_is_installable() -> None:
    path = WEB_PUBLIC / "manifest.webmanifest"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"]
    assert data["short_name"] == "Kestrel"
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"
    assert data["theme_color"] == "#0c0c0c"
    icons = data["icons"]
    assert any(i["sizes"] == "192x192" for i in icons)
    assert any(i["sizes"] == "512x512" for i in icons)
    for icon in icons:
        rel = icon["src"].lstrip("/")
        assert (WEB_PUBLIC / rel).is_file(), icon["src"]


def test_service_worker_shell_precaches_offline() -> None:
    sw = (WEB_PUBLIC / "sw.js").read_text(encoding="utf-8")
    assert "kestrel-shell-v2" in sw
    assert "/offline" in sw
    assert 'url.pathname.startsWith("/api/")' in sw
    # Navigations + Next chunks stay network-first (avoid React #418 vs stale shell).
    assert 'url.pathname.startsWith("/_next/")' in sw
    assert 'req.mode === "navigate"' in sw
    assert (WEB_PUBLIC / "icons" / "icon-192.png").is_file()
    assert (WEB_PUBLIC / "icons" / "icon-512.png").is_file()
    assert (WEB_PUBLIC / "icons" / "apple-touch-icon.png").is_file()
