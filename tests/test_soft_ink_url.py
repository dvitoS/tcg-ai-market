"""SOFT_INK_URL / KESTREL_WEB_URL helper for Streamlit migration banner."""

from __future__ import annotations

import config


def test_get_soft_ink_url_prefers_soft_ink(monkeypatch) -> None:
    monkeypatch.setenv("SOFT_INK_URL", "https://app.example.com/")
    monkeypatch.setenv("KESTREL_WEB_URL", "https://other.example.com")
    assert config.get_soft_ink_url() == "https://app.example.com/"


def test_get_soft_ink_url_falls_back_to_kestrel_web(monkeypatch) -> None:
    monkeypatch.delenv("SOFT_INK_URL", raising=False)
    monkeypatch.setenv("KESTREL_WEB_URL", " https://web.example.com ")
    assert config.get_soft_ink_url() == "https://web.example.com"


def test_get_soft_ink_url_empty_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("SOFT_INK_URL", raising=False)
    monkeypatch.delenv("KESTREL_WEB_URL", raising=False)
    # Avoid picking up Streamlit secrets / leftover env noise in CI.
    monkeypatch.setattr(config, "_from_streamlit_secrets", lambda name: "")
    assert config.get_soft_ink_url() == ""
