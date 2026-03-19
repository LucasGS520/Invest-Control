"""Schemas Pydantic para o Calendário de Proventos (FR5)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, computed_field


class DividendEventOut(BaseModel):
    ticker: str
    asset_name: str | None = None
    value: Decimal
    ex_date: date
    payment_date: date | None
    dividend_type: str

    @computed_field  # type: ignore[misc]
    @property
    def days_until_ex(self) -> int:
        return (self.ex_date - date.today()).days


class PortfolioCalendarOut(BaseModel):
    portfolio_id: int
    upcoming_events: list[DividendEventOut]
    past_events: list[DividendEventOut]


class TickerCalendarOut(BaseModel):
    ticker: str
    upcoming_events: list[DividendEventOut]
    past_events: list[DividendEventOut]
