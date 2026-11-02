"""Smoke tests for config helpers (no live Supabase)."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def config_mod():
    import config

    return importlib.reload(config)


def test_normalize_supabase_url_strips_rest_suffix(config_mod):
    assert (
        config_mod.normalize_supabase_url("https://abc.supabase.co/rest/v1")
        == "https://abc.supabase.co"
    )
    assert (
        config_mod.normalize_supabase_url("https://abc.supabase.co/rest/v1/")
        == "https://abc.supabase.co"
    )


def test_normalize_supabase_url_strips_quotes_and_auth_path(config_mod):
    assert (
        config_mod.normalize_supabase_url(' "https://abc.supabase.co/auth/v1" ')
        == "https://abc.supabase.co"
    )


def test_clean_secret_value_strips_bom_and_quotes(config_mod):
    assert config_mod._clean_secret_value('\ufeff"secret"\n') == "secret"


def test_auth_disabled_true_when_flag_on(config_mod, monkeypatch):
    monkeypatch.setattr(config_mod, "_is_streamlit_cloud", lambda: False)
    monkeypatch.setattr(
        config_mod,
        "_secret",
        lambda name, default="": "1" if name == "AUTH_DISABLED" else default,
    )
    monkeypatch.setattr(
        "dotenv.dotenv_values",
        lambda *_a, **_k: {},
    )
    assert config_mod.auth_disabled() is True


def test_auth_disabled_forced_off_on_streamlit_cloud(config_mod, monkeypatch):
    monkeypatch.setattr(config_mod, "_is_streamlit_cloud", lambda: True)
    monkeypatch.setattr(
        config_mod,
        "_secret",
        lambda name, default="": "1" if name == "AUTH_DISABLED" else default,
    )
    assert config_mod.auth_disabled() is False


def test_get_supabase_auth_credentials_never_falls_back_to_service(config_mod, monkeypatch):
    def fake_secret(name: str, default: str = "") -> str:
        values = {
            "SUPABASE_URL": "https://abc.supabase.co",
            "SUPABASE_KEY": "service-role-key",
            "SUPABASE_ANON_KEY": "",
        }
        return values.get(name, default)

    monkeypatch.setattr(config_mod, "_secret", fake_secret)
    url, anon = config_mod.get_supabase_auth_credentials()
    assert url == "https://abc.supabase.co"
    assert anon == ""


def test_catalog_sets_default_nonempty(config_mod):
    sets = config_mod.catalog_sets()
    assert len(sets) >= 5
    assert all(len(pair) == 2 and pair[0] and pair[1] for pair in sets)


def test_catalog_sets_env_override(config_mod, monkeypatch):
    monkeypatch.setenv("CATALOG_SET_IDS", "sv8:Surging Sparks,swsh7:Evolving Skies")
    monkeypatch.setattr(config_mod, "_secret", lambda name, default="": "")
    sets = config_mod.catalog_sets()
    assert sets == (("sv8", "Surging Sparks"), ("swsh7", "Evolving Skies"))
