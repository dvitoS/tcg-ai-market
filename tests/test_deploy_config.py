"""Smoke checks for deploy config files (no Docker required)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_dockerfile_and_railway_config_exist() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    assert "uvicorn api.main:app" in dockerfile
    assert "python:3.12" in dockerfile
    railway = (ROOT / "railway.api.toml").read_text(encoding="utf-8")
    assert 'dockerfilePath = "Dockerfile.api"' in railway
    assert 'healthcheckPath = "/api/health"' in railway


def test_vercel_and_deploy_docs_exist() -> None:
    vercel = (ROOT / "web" / "vercel.json").read_text(encoding="utf-8")
    assert "nextjs" in vercel
    docs = (ROOT / "docs" / "DEPLOY.md").read_text(encoding="utf-8")
    assert "Creem" in docs
    assert "NEXT_PUBLIC_API_URL" in docs
    assert "KESTREL_CORS_ORIGINS" in docs


def test_dockerignore_excludes_web_node_modules() -> None:
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "web/node_modules" in text
    assert ".env" in text
