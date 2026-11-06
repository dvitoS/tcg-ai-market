"""OCR text → catalog identify (no live camera / tesseract)."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.identify_service import identify_from_text, parse_ocr_clues
from api.main import app


def test_parse_ocr_clues_collector_and_name() -> None:
    raw = """
    Charizard ex
    Basic
    HP 330
    223/197
    Obsidian Flames
    """
    clues = parse_ocr_clues(raw)
    assert clues["number"] == "223"
    assert clues["collector"] and "223" in clues["collector"]
    assert any("charizard" in h.lower() for h in clues["name_hints"])


def test_identify_from_text_ranks_number_and_name(monkeypatch) -> None:
    board = pd.DataFrame(
        [
            {
                "id": "sv3-223",
                "name": "Charizard ex",
                "set_name": "Obsidian Flames",
                "price": 40.0,
                "expected_change_pct": 5.0,
                "signal": "BUY",
                "confidence_ok": True,
            },
            {
                "id": "sv3-6",
                "name": "Charmander",
                "set_name": "Obsidian Flames",
                "price": 1.0,
                "expected_change_pct": 0.0,
                "signal": "HOLD",
                "confidence_ok": True,
            },
            {
                "id": "swsh7-20",
                "name": "Pikachu",
                "set_name": "Evolving Skies",
                "price": 2.0,
                "expected_change_pct": -1.0,
                "signal": "SELL",
                "confidence_ok": True,
            },
        ]
    )
    monkeypatch.setattr(
        "api.identify_service.load_board",
        lambda: (board, "demo"),
    )
    out = identify_from_text("Charizard ex\n223/197\nObsidian Flames", limit=5)
    assert out["total"] >= 1
    top = out["matches"][0]["card"]
    assert top["id"] == "sv3-223"
    assert "number" in out["matches"][0]["reasons"] or "name" in out["matches"][0]["reasons"]


def test_identify_api_endpoint(monkeypatch) -> None:
    board = pd.DataFrame(
        [
            {
                "id": "sv3-25",
                "name": "Pikachu",
                "set_name": "Obsidian Flames",
                "price": 3.5,
                "expected_change_pct": 2.0,
                "signal": "BUY",
                "confidence_ok": True,
            }
        ]
    )
    monkeypatch.setattr(
        "api.identify_service.load_board",
        lambda: (board, "demo"),
    )
    client = TestClient(app)
    res = client.post(
        "/api/identify",
        json={"text": "Pikachu\n025/197\nObsidian Flames", "limit": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["matches"]
    assert body["matches"][0]["card"]["id"] == "sv3-25"
    assert body["number"] == "25"


def test_identify_api_rejects_empty() -> None:
    client = TestClient(app)
    res = client.post("/api/identify", json={"text": "ab"})
    assert res.status_code == 422 or res.status_code == 400
