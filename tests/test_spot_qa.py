"""Phase C2 spot / history QA helpers."""

from __future__ import annotations

from services import spot_qa


def test_save_and_load_local_snapshot(tmp_path, monkeypatch) -> None:
    path = tmp_path / "spot_qa.json"
    monkeypatch.setattr(spot_qa, "LOCAL_PATH", path)

    import database

    monkeypatch.setattr(
        database,
        "get_supabase",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    ok = spot_qa.save_spot_qa_snapshot(
        {
            "history_coverage_pct": 80.0,
            "fresh_history_pct": 55.0,
            "sure_rows": 12,
            "unmatched_sets_count": 2,
            "unmatched_sets_sample": [
                {"set_code": "sv2", "set_name": "Paldea Evolved"}
            ],
        }
    )
    assert ok is True
    loaded = spot_qa.load_spot_qa_snapshot()
    assert loaded is not None
    assert loaded["history_coverage_pct"] == 80.0
    assert loaded["unmatched_sets_count"] == 2


def test_data_health_spot_fields_merge(monkeypatch) -> None:
    def _live(**_kwargs):
        return {
            "cards_total": 100,
            "cards_with_history": 0,
            "history_coverage_pct": 0.0,
            "history_scan": False,
            "quotes_total": 50,
            "sure_rows": 20,
            "spot_quarantine_rows": 12,
            "spot_poison_clusters": 1,
            "spot_poison_cluster_sample": [{"price": 68.15, "count": 12, "sets": 4}],
            "board_source": "demo",
        }

    monkeypatch.setattr(spot_qa, "compute_live_spot_qa", _live)
    monkeypatch.setattr(
        spot_qa,
        "load_spot_qa_snapshot",
        lambda: {
            "cards_with_history": 70,
            "history_coverage_pct": 70.0,
            "fresh_history_pct": 40.0,
            "unmatched_sets_count": 3,
            "unmatched_sets_sample": [{"set_code": "x", "set_name": "X"}],
            "captured_at": "2026-11-05T12:00:00+00:00",
        },
    )
    fields = spot_qa.data_health_spot_fields()
    assert fields["sure_rows"] == 20
    # Coverage comes from nightly snapshot — live path skips the 2M-row scan.
    assert fields["history_coverage_pct"] == 70.0
    assert fields["cards_with_history"] == 70
    assert fields["fresh_history_pct"] == 40.0
    assert fields["unmatched_sets_count"] == 3
    assert fields["spot_qa_captured_at"] == "2026-11-05T12:00:00+00:00"
    assert fields["spot_quarantine_rows"] == 12
    assert fields["spot_poison_clusters"] == 1


def test_data_health_skips_history_distinct_scan(monkeypatch) -> None:
    """Regression: live data-health must not fetch_all(price_history)."""
    calls: list[str] = []

    def boom_distinct():
        calls.append("distinct")
        raise AssertionError("must not scan price_history on API data-health")

    monkeypatch.setattr(
        "database.distinct_history_card_ids",
        boom_distinct,
        raising=False,
    )
    monkeypatch.setattr(
        spot_qa,
        "load_spot_qa_snapshot",
        lambda: {"history_coverage_pct": 95.0, "cards_with_history": 20000},
    )
    monkeypatch.setattr(
        spot_qa,
        "compute_live_spot_qa",
        lambda **kwargs: (
            calls.append(f"live:{kwargs.get('include_history_scan')}")
            or {
                "cards_total": 10,
                "cards_with_history": 0,
                "history_coverage_pct": 0.0,
                "history_scan": False,
                "quotes_total": 5,
                "sure_rows": 2,
                "spot_quarantine_rows": 0,
                "spot_poison_clusters": 0,
                "spot_poison_cluster_sample": [],
                "board_source": "supabase",
            }
        ),
    )
    fields = spot_qa.data_health_spot_fields()
    assert "distinct" not in calls
    assert calls == ["live:False"]
    assert fields["history_coverage_pct"] == 95.0


def test_data_health_endpoint_includes_spot_fields(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from api.main import app
    from services import prices as prices_mod

    prices_mod.reset_justtcg_observability()
    monkeypatch.setattr(
        "services.spot_qa.data_health_spot_fields",
        lambda: {
            "cards_total": 10,
            "cards_with_history": 8,
            "history_coverage_pct": 80.0,
            "fresh_history_pct": 50.0,
            "sure_rows": 4,
            "quotes_total": 9,
            "spot_quarantine_rows": 12,
            "spot_poison_clusters": 1,
            "spot_poison_cluster_sample": [{"price": 68.15, "count": 12, "sets": 4}],
            "unmatched_sets_count": 1,
            "unmatched_sets_sample": [{"set_code": "sv9", "set_name": "Journey Together"}],
            "spot_qa_captured_at": "2026-11-05T12:00:00+00:00",
            "board_source": "demo",
        },
    )
    client = TestClient(app)
    resp = client.get("/api/data-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["history_coverage_pct"] == 80.0
    assert body["sure_rows"] == 4
    assert body["unmatched_sets_count"] == 1
    assert body["fresh_history_pct"] == 50.0
    assert body["spot_quarantine_rows"] == 12
    assert body["spot_poison_clusters"] == 1
