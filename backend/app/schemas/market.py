"""Schemas Pydantic para dados de mercado, DY e preço-teto."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class QuoteOut(BaseModel):
    ticker: str
    price: Decimal
    change_percent: Decimal | None
    volume: Decimal | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class DividendOut(BaseModel):
    id: int
    ticker: str
    value: Decimal
    ex_date: date
    payment_date: date | None
    dividend_type: str

    model_config = {"from_attributes": True}


class DYOut(BaseModel):
    ticker: str
    current_dy: Decimal | None
    months: int


class DYHistoryItem(BaseModel):
    year: int
    total_dividends: Decimal
    dy_percent: Decimal | None


class DYHistoryOut(BaseModel):
    ticker: str
    history: list[DYHistoryItem]


class CeilingOut(BaseModel):
    ticker: str
    barsi_ceiling: Decimal | None
    current_price: Decimal | None
    current_dy: Decimal | None
    desired_dy: Decimal
    is_below_ceiling: bool
    ceiling_distance_pct: Decimal | None


class AssetSearchResult(BaseModel):
    ticker: str
    name: str
    sector: str | None
    asset_type: str
    price: Decimal | None = None
    change_percent: Decimal | None = None


class UserPositionContext(BaseModel):
    portfolio_id: int
    portfolio_name: str
    quantity: int
    avg_price: Decimal
    current_value: Decimal | None = None
    return_pct: Decimal | None = None


class AssetDetailOut(BaseModel):
    ticker: str
    name: str
    sector: str | None
    asset_type: str
    price: Decimal | None = None
    change_percent: Decimal | None = None
    volume: Decimal | None = None
    positions: list[UserPositionContext] = []
    total_dividends_received: Decimal | None = None
