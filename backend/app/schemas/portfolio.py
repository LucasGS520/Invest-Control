"""Schemas Pydantic para carteiras e posições."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    objective: str | None = Field(None, max_length=200)
    currency: str = Field("BRL", max_length=10)


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    objective: str | None = Field(None, max_length=200)
    currency: str | None = Field(None, max_length=10)


class PortfolioOut(BaseModel):
    id: int
    name: str
    description: str | None
    objective: str | None
    currency: str
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
    current_price: Decimal | None = None
    current_value: Decimal | None = None
    return_pct: Decimal | None = None
    change_percent: Decimal | None = None

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    id: int
    name: str
    description: str | None
    objective: str | None
    currency: str
    created_at: datetime
    total_invested: Decimal
    positions: list[PositionOut]

    model_config = {"from_attributes": True}
