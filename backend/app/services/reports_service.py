"""Serviço de Relatórios de Performance e Renda de Dividendos (FR7).

Três relatórios principais:
1. Performance: retorno total por carteira e por posição.
2. Dividend Income: renda mensal de proventos dos últimos 12 meses.
3. Projections: projeção de renda passiva anual/mensal com base no histórico.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.schemas.reports import (
    DividendIncomeReport,
    MonthlyIncome,
    PerformanceReport,
    PositionPerformance,
    PositionProjection,
    ProjectionReport,
)

_MONTHS_ABBR = [
    "", "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _load_portfolio(db: AsyncSession, portfolio: Portfolio) -> Portfolio:
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.positions).selectinload(PortfolioAsset.asset))
        .where(Portfolio.id == portfolio.id)
    )
    return result.scalar_one()


async def _current_price(db: AsyncSession, ticker: str) -> Decimal | None:
    row = await db.execute(select(MarketQuote.price).where(MarketQuote.ticker == ticker))
    val = row.scalar_one_or_none()
    return Decimal(str(val)) if val else None


# ──────────────────────────────────────────────────────────────────────────────
# 1. Relatório de Performance
# ──────────────────────────────────────────────────────────────────────────────


async def get_performance_report(
    db: AsyncSession,
    portfolio: Portfolio,
) -> PerformanceReport:
    """Retorna retorno total por carteira e por posição."""
    loaded = await _load_portfolio(db, portfolio)
    active = [p for p in loaded.positions if p.quantity > 0]

    total_invested = Decimal("0")
    total_current = Decimal("0")
    position_perfs: list[PositionPerformance] = []

    for pos in active:
        ticker = pos.asset.ticker
        avg = Decimal(str(pos.avg_price))
        invested = _q2(Decimal(str(pos.quantity)) * avg)

        price = await _current_price(db, ticker)
        current_val = _q2(Decimal(str(pos.quantity)) * price) if price else None
        ret_val = _q2(current_val - invested) if current_val is not None else None
        ret_pct = (
            _q2((ret_val / invested * Decimal("100")) if invested > 0 else Decimal("0"))
            if ret_val is not None
            else None
        )

        total_invested += invested
        total_current += current_val if current_val is not None else invested

        position_perfs.append(
            PositionPerformance(
                ticker=ticker,
                asset_name=pos.asset.name,
                asset_type=pos.asset.asset_type,
                quantity=pos.quantity,
                avg_price=avg,
                current_price=price,
                invested=invested,
                current_value=current_val,
                return_value=ret_val,
                return_pct=ret_pct,
            )
        )

    total_return = _q2(total_current - total_invested)
    total_return_pct = (
        _q2(total_return / total_invested * Decimal("100"))
        if total_invested > 0
        else None
    )

    # Ordena por retorno % decrescente (None por último)
    position_perfs.sort(
        key=lambda p: p.return_pct if p.return_pct is not None else Decimal("-999"),
        reverse=True,
    )

    return PerformanceReport(
        portfolio_id=portfolio.id,
        portfolio_name=loaded.name,
        total_invested=_q2(total_invested),
        current_value=_q2(total_current),
        total_return=total_return,
        total_return_pct=total_return_pct,
        positions=position_perfs,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 2. Renda de Dividendos
# ──────────────────────────────────────────────────────────────────────────────


async def get_dividend_income_report(
    db: AsyncSession,
    portfolio: Portfolio,
) -> DividendIncomeReport:
    """Renda mensal de proventos dos últimos 12 meses.

    Simplificação: usa a quantidade atual de cada posição para calcular a
    renda estimada de cada mês (não rastreia quantidade histórica por data).
    """
    loaded = await _load_portfolio(db, portfolio)
    active = [p for p in loaded.positions if p.quantity > 0]

    # Mapa: ticker → quantidade atual
    qty_map: dict[str, int] = {pos.asset.ticker: pos.quantity for pos in active}

    today = date.today()
    cutoff = today - timedelta(days=365)

    tickers = list(qty_map.keys())
    if not tickers:
        return DividendIncomeReport(
            portfolio_id=portfolio.id,
            monthly_income=[],
            total_12m=Decimal("0"),
            avg_monthly_12m=Decimal("0"),
        )

    div_result = await db.execute(
        select(Dividend).where(
            Dividend.ticker.in_(tickers),
            Dividend.ex_date >= cutoff,
            Dividend.ex_date <= today,
        )
    )
    dividends = div_result.scalars().all()

    # Agrupa por (year, month)
    monthly: dict[tuple[int, int], Decimal] = {}
    for d in dividends:
        key = (d.ex_date.year, d.ex_date.month)
        per_share = Decimal(str(d.value))
        qty = Decimal(str(qty_map.get(d.ticker, 0)))
        monthly[key] = monthly.get(key, Decimal("0")) + per_share * qty

    # Gera lista dos últimos 12 meses, independente de ter dividendos
    result_months: list[MonthlyIncome] = []
    for offset in range(12):
        ref = today.replace(day=1) - timedelta(days=offset * 28)
        ref = ref.replace(day=1)
        key = (ref.year, ref.month)
        label = f"{_MONTHS_ABBR[ref.month]}/{ref.year}"
        result_months.append(
            MonthlyIncome(
                year=ref.year,
                month=ref.month,
                month_label=label,
                total_value=_q2(monthly.get(key, Decimal("0"))),
            )
        )

    total_12m = _q2(sum(m.total_value for m in result_months))
    avg_monthly = _q2(total_12m / Decimal("12"))

    return DividendIncomeReport(
        portfolio_id=portfolio.id,
        monthly_income=result_months,
        total_12m=total_12m,
        avg_monthly_12m=avg_monthly,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3. Projeções de Renda Passiva
# ──────────────────────────────────────────────────────────────────────────────


async def get_projection_report(
    db: AsyncSession,
    portfolio: Portfolio,
) -> ProjectionReport:
    """Projeção de renda passiva anual/mensal baseada nos últimos 12 meses."""
    loaded = await _load_portfolio(db, portfolio)
    active = [p for p in loaded.positions if p.quantity > 0]

    today = date.today()
    cutoff = today - timedelta(days=365)

    total_current_value = Decimal("0")
    total_annual_income = Decimal("0")
    position_projections: list[PositionProjection] = []

    weighted_dy_num = Decimal("0")   # para DY médio ponderado
    weighted_dy_den = Decimal("0")

    for pos in active:
        ticker = pos.asset.ticker
        qty = Decimal(str(pos.quantity))

        # Cotação atual (ou avg_price como fallback)
        price = await _current_price(db, ticker)
        pos_value = qty * (price or Decimal(str(pos.avg_price)))
        total_current_value += pos_value

        # Dividendos últimos 12 meses para este ticker
        div_result = await db.execute(
            select(Dividend).where(
                Dividend.ticker == ticker,
                Dividend.ex_date >= cutoff,
                Dividend.ex_date <= today,
            )
        )
        divs = div_result.scalars().all()
        dividends_per_share = sum(Decimal(str(d.value)) for d in divs)

        annual_income = _q2(dividends_per_share * qty)
        monthly_income = _q2(annual_income / Decimal("12"))
        total_annual_income += annual_income

        # DY por posição
        dy: Decimal | None = None
        if price and price > 0 and dividends_per_share > 0:
            dy = _q2(dividends_per_share / price * Decimal("100"))
            weighted_dy_num += dy * pos_value
            weighted_dy_den += pos_value

        position_projections.append(
            PositionProjection(
                ticker=ticker,
                asset_name=pos.asset.name,
                quantity=int(qty),
                annual_income=annual_income,
                monthly_income=monthly_income,
                dy=dy,
            )
        )

    # DY médio ponderado pelo valor da posição
    avg_dy = (
        _q2(weighted_dy_num / weighted_dy_den)
        if weighted_dy_den > 0
        else None
    )

    # Ordena por renda anual decrescente
    position_projections.sort(key=lambda p: p.annual_income, reverse=True)

    return ProjectionReport(
        portfolio_id=portfolio.id,
        current_value=_q2(total_current_value),
        projected_annual_income=_q2(total_annual_income),
        projected_monthly_income=_q2(total_annual_income / Decimal("12")),
        avg_dy=avg_dy,
        positions=position_projections,
    )
