"""Schemas Pydantic para transações de compra e venda."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    asset_id: int
    transaction_type: Literal["BUY", "SELL"]
    quantity: int = Field(..., gt=0)
    price: Decimal = Field(..., gt=0, decimal_places=4)
    date: date
    notes: str | None = None


class TransactionOut(BaseModel):
    id: int
    portfolio_id: int
    asset_id: int
    ticker: str
    transaction_type: str
    quantity: int
    price: Decimal
    date: date
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
