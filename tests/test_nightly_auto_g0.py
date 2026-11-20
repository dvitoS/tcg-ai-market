"""Nightly auto G0 sniff + heal (ops-free)."""

from __future__ import annotations

from services import spot_sniff


def test_run_nightly_auto_g0_skipped_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("NIGHTLY_AUTO_G0", "0")
    out = spot_sniff.run_nightly_auto_g0()
    assert out["skipped"] is True
    assert out["reason"] == "NIGHTLY_AUTO_G0=0"


def test_run_nightly_auto_g0_persists_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("NIGHTLY_AUTO_G0", "1")
    monkeypatch.setenv("NIGHTLY_G0_REQUIRED", "0")
    monkeypatch.setenv("NIGHTLY_AUTO_G0_LIMIT", "20")
    monkeypatch.setattr(
        "ebay_client.ebay_sold_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "api.catalog_service.clear_board_cache",
        lambda: None,
    )

    pack = {
        "generated_at": "2026-11-10T00:00:00+00:00",
        "count": 20,
        "g0_ready": True,
        "verdict_pass": 19,
        "verdict_review": 1,
        "verdict_fail": 0,
        "healed_n": 2,
        "healed_ids": ["a", "b"],
        "tcp_missing": 0,
        "tcp_resolved": 1,
        "auto_ok": 18,
        "auto_fail": 2,
        "live_checked": True,
    }
    monkeypatch.setattr(
        spot_sniff,
        "build_spot_sniff_pack",
        lambda **kwargs: pack,
    )

    saved: dict = {}

    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {"sure_rows": 40},
    )

    def _save(payload):
        saved.update(payload)
        return True

    monkeypatch.setattr("services.spot_qa.save_spot_qa_snapshot", _save)

    out = spot_sniff.run_nightly_auto_g0()
    assert out["skipped"] is False
    assert out["g0_ready"] is True
    assert out["ebay_check"] is False
    assert out["healed_n"] == 2
    assert out["required"] is False
    assert saved.get("g0_ready") is True
    assert saved["nightly_auto_g0"]["verdict_pass"] == 19
    assert saved["nightly_auto_g0"]["source"] == "nightly"
    assert saved.get("sure_rows") == 40


def test_persist_auto_g0_snapshot_manual(monkeypatch) -> None:
    saved: dict = {}
    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {"sure_rows": 12},
    )

    def _save(payload):
        saved.update(payload)
        return True

    monkeypatch.setattr("services.spot_qa.save_spot_qa_snapshot", _save)

    pack = {
        "generated_at": "2026-11-20T03:00:00+00:00",
        "limit": 20,
        "count": 20,
        "g0_ready": True,
        "verdict_pass": 18,
        "verdict_review": 2,
        "verdict_fail": 0,
        "healed_n": 1,
        "healed_ids": ["card-1"],
        "tcp_missing": 0,
        "tcp_resolved": 0,
        "auto_ok": 18,
        "auto_fail": 1,
        "live_checked": True,
        "ebay_checked": False,
    }
    out = spot_sniff.persist_auto_g0_snapshot(pack, source="manual", limit=20)
    assert out["persisted"] is True
    assert out["g0_ready"] is True
    assert saved["g0_ready"] is True
    assert saved["nightly_auto_g0"]["source"] == "manual"
    assert saved["nightly_auto_g0"]["verdict_pass"] == 18
    assert saved["nightly_auto_g0"]["captured_at"] == "2026-11-20T03:00:00+00:00"


def test_nightly_auto_g0_required_flag(monkeypatch) -> None:
    monkeypatch.setenv("NIGHTLY_G0_REQUIRED", "1")
    assert spot_sniff.nightly_auto_g0_required() is True
    monkeypatch.setenv("NIGHTLY_G0_REQUIRED", "0")
    assert spot_sniff.nightly_auto_g0_required() is False
