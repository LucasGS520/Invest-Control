"""Schemas Pydantic para ativos negociados."""

from typing import Literal

from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    ticker: str = Field(..., min_length=4, max_length=10, pattern=r"^[A-Z0-9]+$")
    name: str = Field(..., min_length=2, max_length=200)
    sector: str | None = Field(None, max_length=100)
    asset_type: Literal["ACAO", "FII"]


class AssetOut(BaseModel):
    id: int
    ticker: str
    name: str
    sector: str | None
    asset_type: str
    is_active: bool

    model_config = {"from_attributes": True}
