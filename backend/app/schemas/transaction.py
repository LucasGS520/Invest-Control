"""Schemas Pydantic para transações de compra e venda."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    ticker: str = Field(..., min_length=4, max_length=20, pattern=r"^[A-Z0-9]+$")
    transaction_type: Literal["BUY", "SELL"]
    quantity: int = Field(..., gt=0)
    price: Decimal = Field(..., gt=0, decimal_places=4)
    fees: Decimal | None = Field(None, ge=0, decimal_places=4)
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
    fees: Decimal | None
    date: date
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
