"""Schemas Pydantic para carteiras e posições."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None


class PortfolioOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionOut(BaseModel):
    id: int
    asset_id: int
    ticker: str
    asset_name: str
    asset_type: str
    quantity: int
    avg_price: Decimal

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    total_invested: Decimal
    positions: list[PositionOut]

    model_config = {"from_attributes": True}
