"""PSA Public API client — cert + population (no live token)."""

from __future__ import annotations

import psa_public_client as psa


class _Resp:
    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_normalize_cert_from_url() -> None:
    assert psa.normalize_cert_number("https://www.psacard.com/cert/83179580") == "83179580"
    assert psa.normalize_cert_number(" 83-179-580 ") == "83179580"


def test_summarize_population_gem_rate() -> None:
    summary = psa.summarize_population(
        {
            "SpecID": 42,
            "Description": "Demo",
            "PSAPop": {"Total": 200, "Grade9": 40, "Grade10": 20},
        }
    )
    assert summary["gem_rate_pct"] == 10.0
    assert summary["grade10"] == 20
    assert summary["total"] == 200


def test_lookup_cert_pack(monkeypatch) -> None:
    psa.reset_psa_public_budget_for_tests()
    monkeypatch.setenv("PSA_PUBLIC_API_TOKEN", "test-token")
    monkeypatch.setenv("PSA_PUBLIC_DAILY_BUDGET", "10")

    calls: list[str] = []

    def _get(url, headers=None, timeout=None):
        calls.append(url)
        if "GetByCertNumber" in url:
            return _Resp(
                200,
                {
                    "PSACert": {
                        "CertNumber": "83179580",
                        "SpecID": 99,
                        "Subject": "Charizard",
                        "Brand": "Pokemon",
                        "CardGrade": "10",
                        "Year": "1999",
                    },
                    "IsValidRequest": True,
                },
            )
        if "GetPSASpecPopulation" in url:
            return _Resp(
                200,
                {
                    "SpecID": 99,
                    "Description": "Charizard",
                    "PSAPop": {"Total": 100, "Grade9": 30, "Grade10": 25},
                },
            )
        return _Resp(404, {})

    monkeypatch.setattr(psa.requests, "get", _get)
    pack = psa.lookup_cert_pack("83179580", include_pop=True)
    assert pack["cert_number"] == "83179580"
    assert pack["subject"] == "Charizard"
    assert pack["gem_rate_pct"] == 25.0
    assert pack["pop_grade10"] == 25
    assert any("GetByCertNumber" in u for u in calls)
    assert any("GetPSASpecPopulation" in u for u in calls)

    # Second call should hit cache (no extra HTTP for cert).
    before = len(calls)
    again = psa.lookup_cert_pack("83179580", include_pop=True)
    assert again["gem_rate_pct"] == 25.0
    assert len(calls) == before


def test_psa_cert_endpoint(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    psa.reset_psa_public_budget_for_tests()
    monkeypatch.setenv("PSA_PUBLIC_API_TOKEN", "test-token")

    monkeypatch.setattr(
        "api.routers.psa.lookup_cert_pack",
        lambda cert, include_pop=True: {
            "configured": True,
            "cert_number": "1",
            "spec_id": 2,
            "subject": "Pikachu",
            "brand": "Pokemon",
            "category": "TCG Cards",
            "variety": None,
            "year": "2020",
            "card_number": "25",
            "grade": "9",
            "label_type": "Standard",
            "total_population": None,
            "population_higher": None,
            "pop_total": 50,
            "pop_grade9": 10,
            "pop_grade10": 5,
            "pop_description": "Pikachu",
            "gem_rate_pct": 10.0,
            "source": "psa_public_api",
        },
    )
    monkeypatch.setattr("api.routers.psa.psa_public_configured", lambda: True)

    client = TestClient(app)
    res = client.get("/api/psa/cert/1")
    assert res.status_code == 200
    assert res.json()["gem_rate_pct"] == 10.0

    status = client.get("/api/psa/status")
    assert status.status_code == 200
    assert status.json()["provides_market_prices"] is False
