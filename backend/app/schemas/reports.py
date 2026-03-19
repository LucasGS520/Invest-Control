"""Schemas Pydantic para Relatórios de Performance (FR7)."""

from decimal import Decimal

from pydantic import BaseModel


class PositionPerformance(BaseModel):
    ticker: str
    asset_name: str
    asset_type: str
    quantity: int
    avg_price: Decimal
    current_price: Decimal | None
    invested: Decimal
    current_value: Decimal | None
    return_value: Decimal | None    # current_value - invested
    return_pct: Decimal | None      # % retorno sobre custo


class PerformanceReport(BaseModel):
    portfolio_id: int
    portfolio_name: str
    total_invested: Decimal
    current_value: Decimal          # usa avg_price quando sem cotação
    total_return: Decimal
    total_return_pct: Decimal | None
    positions: list[PositionPerformance]


class MonthlyIncome(BaseModel):
    year: int
    month: int
    month_label: str                # "jan/2025"
    total_value: Decimal            # soma dos proventos do mês × qtd posição


class DividendIncomeReport(BaseModel):
    portfolio_id: int
    monthly_income: list[MonthlyIncome]   # últimos 12 meses, mais recente primeiro
    total_12m: Decimal
    avg_monthly_12m: Decimal


class PositionProjection(BaseModel):
    ticker: str
    asset_name: str
    quantity: int
    annual_income: Decimal          # últimos 12m dividendos × qtd
    monthly_income: Decimal
    dy: Decimal | None


class ProjectionReport(BaseModel):
    portfolio_id: int
    current_value: Decimal
    projected_annual_income: Decimal
    projected_monthly_income: Decimal
    avg_dy: Decimal | None          # DY médio ponderado pela posição
    positions: list[PositionProjection]
