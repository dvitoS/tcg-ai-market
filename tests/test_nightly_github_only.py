"""Nightly must run via GitHub Actions unless explicitly overridden."""

from __future__ import annotations

import nightly_update as nightly
import schedule_setup


def test_nightly_blocked_without_github(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("NIGHTLY_ALLOW_LOCAL", raising=False)
    allowed, reason = nightly.nightly_runner_allowed()
    assert allowed is False
    assert reason == "blocked"
    assert nightly.main() == 2


def test_nightly_allowed_on_github_actions(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("NIGHTLY_ALLOW_LOCAL", raising=False)
    allowed, reason = nightly.nightly_runner_allowed()
    assert allowed is True
    assert reason == "github_actions"


def test_nightly_allowed_with_local_override(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("NIGHTLY_ALLOW_LOCAL", "1")
    allowed, reason = nightly.nightly_runner_allowed()
    assert allowed is True
    assert reason == "local_override"


def test_schedule_setup_refuses_local_install(capsys) -> None:
    assert schedule_setup.main() == 1
    err = capsys.readouterr().err
    assert "GitHub Actions" in err or "no longer creates" in err
