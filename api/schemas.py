"""Pydantic response / request models for the public API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "kestrel-api"
    source: Literal["supabase", "demo", "empty"] = "empty"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    dev: bool = False


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    user: AuthUser


class MeResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None


class CatalogCard(BaseModel):
    id: str
    name: str
    set_name: str | None = None
    rarity: str | None = None
    supertype: str | None = None
    price: float | None = None
    market_price: float | None = None
    predicted_price: float | None = None
    expected_change_pct: float | None = None
    price_change_7d_pct: float | None = None
    signal: str | None = None
    confidence_ok: bool = True
    conformal_ok: bool = True
    confidence_level: str | None = None
    history_points: int = 0
    image_url: str | None = None


class CatalogMeta(BaseModel):
    total: int
    sets: list[str] = Field(default_factory=list)
    signals: dict[str, int] = Field(default_factory=dict)
    price_min: float = 0.0
    price_max: float = 100.0
    source: Literal["supabase", "demo", "empty"] = "empty"


class CatalogResponse(BaseModel):
    items: list[CatalogCard]
    total: int
    limit: int
    offset: int
    meta: CatalogMeta


class CardDetailResponse(BaseModel):
    card: CatalogCard
    pred_lo_pct: float | None = None
    pred_hi_pct: float | None = None


class HistoryPoint(BaseModel):
    date: str
    price: float


class CardHistoryResponse(BaseModel):
    card_id: str
    points: list[HistoryPoint]


class SignalBoardResponse(BaseModel):
    buys: list[CatalogCard]
    sells: list[CatalogCard]
    holds: list[CatalogCard]
    source: Literal["supabase", "demo", "empty"] = "empty"
