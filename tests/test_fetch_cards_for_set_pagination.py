"""Regression: pokemontcg.io orderBy=number breaks multi-page set fetches."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _card(cid: str) -> dict:
    return {"id": cid, "name": cid, "images": {"small": f"https://img/{cid}.png"}}


def test_fetch_cards_for_set_does_not_send_order_by(monkeypatch):
    import pokemon_tcg_client as ptcg

    seen_params: list[dict] = []

    def fake_get(url, params, progress=None):
        seen_params.append(dict(params))
        page = int(params.get("page") or 1)
        if page == 1:
            return {
                "data": [_card(f"me2pt5-{n}") for n in range(1, 251)],
                "totalCount": 295,
            }
        return {
            "data": [_card(f"me2pt5-{n}") for n in range(251, 296)],
            "totalCount": 295,
        }

    monkeypatch.setattr(ptcg, "_pokemon_get", fake_get)
    monkeypatch.setattr(ptcg, "_pace_after_page", lambda *a, **k: None)
    monkeypatch.setattr(ptcg, "rate_limit_sleep_seconds", lambda: 0)

    cards = ptcg.fetch_cards_for_set("me2pt5", set_name="Ascended Heroes", page_size=250)
    assert len(cards) == 295
    assert {c["id"] for c in cards} == {f"me2pt5-{n}" for n in range(1, 296)}
    assert all("orderBy" not in p for p in seen_params)
    assert [p["page"] for p in seen_params] == [1, 2]


def test_fetch_cards_for_set_dedupes_overlapping_pages(monkeypatch):
    """Simulate the broken orderBy windows we saw live (page2 ⊂ page1)."""
    import pokemon_tcg_client as ptcg

    page1_ids = [f"me2pt5-{n}" for n in range(1, 251)]
    # Overlap: page 2 only repeats ids already on page 1.
    page2_ids = page1_ids[50:95]

    def fake_get(url, params, progress=None):
        page = int(params.get("page") or 1)
        ids = page1_ids if page == 1 else page2_ids
        return {"data": [_card(i) for i in ids], "totalCount": 295}

    monkeypatch.setattr(ptcg, "_pokemon_get", fake_get)
    monkeypatch.setattr(ptcg, "_pace_after_page", lambda *a, **k: None)
    monkeypatch.setattr(ptcg, "_append_automation_log", MagicMock())

    cards = ptcg.fetch_cards_for_set("me2pt5", set_name="Ascended Heroes", page_size=250)
    assert len(cards) == 250
    ptcg._append_automation_log.assert_called()
    warn = " ".join(
        str(c.args[0]) for c in ptcg._append_automation_log.call_args_list
    )
    assert "0 new ids" in warn or "incomplete" in warn


def test_fetch_cards_ingest_keeps_full_unique_set(monkeypatch):
    import pokemon_tcg_client as ptcg

    def fake_set(sid, set_name=None, page_size=250):
        return [_card(f"{sid}-{n}") for n in range(1, 296)]

    monkeypatch.setattr(ptcg, "fetch_cards_for_set", fake_set)
    monkeypatch.setattr(ptcg, "rate_limit_sleep_seconds", lambda: 0)

    cards = ptcg.fetch_cards(set_ids=[("me2pt5", "Ascended Heroes")])
    assert len(cards) == 295
