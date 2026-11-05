"""Golden tests for JustTCG set matching (Phase C1)."""

from __future__ import annotations

from types import SimpleNamespace

from justtcg_client import (
    pick_justtcg_set_id,
    resolve_set_id,
    score_justtcg_set_row,
    set_code_variants,
)
from sync_justtcg import _display_set_name


ALT = {
    "id": "alternate-art-promos-pokemon",
    "name": "Alternate Art Promos",
}
SV10 = {"id": "sv10-destined-rivals-pokemon", "name": "Destined Rivals"}
SV151 = {"id": "sv-scarlet-violet-151-pokemon", "name": "151"}
ES = {"id": "swsh07-evolving-skies-pokemon", "name": "Evolving Skies"}
PE = {"id": "sv02-paldea-evolved-pokemon", "name": "Paldea Evolved"}
PF = {"id": "sv4pt5-paldean-fates-pokemon", "name": "Paldean Fates"}


def test_set_code_variants_zero_pad():
    variants = set_code_variants("swsh7")
    assert "swsh7" in variants
    assert "swsh07" in variants


def test_never_pick_first_row_promo_fallback():
    rows = [ALT, SV10, SV151, ES]
    assert pick_justtcg_set_id(rows, set_name="sv2", set_code="sv2") is None
    assert pick_justtcg_set_id(rows, set_name="sv1", set_code="sv1") is None


def test_exact_name_beats_first_row():
    rows = [ALT, SV151, ES]
    assert pick_justtcg_set_id(rows, set_name="151") == SV151["id"]
    assert (
        pick_justtcg_set_id(rows, set_name="Evolving Skies", set_code="swsh7")
        == ES["id"]
    )


def test_code_token_match_with_zero_pad():
    rows = [ALT, ES, PE]
    assert (
        pick_justtcg_set_id(rows, set_name="swsh7", set_code="swsh7") == ES["id"]
    )
    assert (
        pick_justtcg_set_id(rows, set_name="Paldea Evolved", set_code="sv2")
        == PE["id"]
    )


def test_paldean_fates_code():
    rows = [ALT, PF, PE]
    assert (
        pick_justtcg_set_id(rows, set_name="Paldean Fates", set_code="sv4pt5")
        == PF["id"]
    )


def test_score_rejects_unrelated_first_hit():
    assert score_justtcg_set_row(ALT, wanted_name="sv2", set_code="sv2") is None
    assert score_justtcg_set_row(SV10, wanted_name="sv1", set_code="sv1") is None


def test_resolve_set_id_no_silent_rows0(monkeypatch):
    calls: list[dict] = []

    def fake_get(path, params=None):
        calls.append(dict(params or {}))
        return {"data": [ALT, SV10, ES]}

    monkeypatch.setattr("justtcg_client._get", fake_get)
    monkeypatch.setattr(
        "justtcg_client.list_pokemon_sets",
        lambda: [ALT, SV10, ES],
    )
    assert resolve_set_id("sv1", set_code="sv1") is None
    assert resolve_set_id("Evolving Skies", set_code="swsh7") == ES["id"]


def test_resolve_caches_negative(monkeypatch):
    cache: dict[str, str] = {}
    monkeypatch.setattr(
        "justtcg_client._get",
        lambda path, params=None: {"data": [ALT]},
    )
    monkeypatch.setattr("justtcg_client.list_pokemon_sets", lambda: [ALT])
    assert resolve_set_id("sv8", set_code="sv8", cache=cache) is None
    assert cache  # negative cached
    # Second call must not hit network again — blow up if _get is used.
    monkeypatch.setattr(
        "justtcg_client._get",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("should use cache")),
    )
    assert resolve_set_id("sv8", set_code="sv8", cache=cache) is None


def test_display_set_name_prefers_card_majority():
    cards = [
        ( "1", SimpleNamespace(set_name="Paldea Evolved", id="sv2-1") ),
        ( "2", SimpleNamespace(set_name="Paldea Evolved", id="sv2-2") ),
        ( "3", SimpleNamespace(set_name="sv2", id="sv2-3") ),
    ]
    assert _display_set_name("sv2", cards) == "Paldea Evolved"


def test_display_set_name_falls_back_to_code():
    cards = [("1", SimpleNamespace(set_name=None, id="xyz-1"))]
    assert _display_set_name("xyz", cards) == "xyz"
