"""Endpoints de Relatórios de Performance e Dividendos (FR7).

GET /api/reports/performance?portfolio_id=X   — retorno total por carteira
GET /api/reports/dividend-income?portfolio_id=X — renda mensal de dividendos
GET /api/reports/projections?portfolio_id=X   — projeção de renda passiva
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.portfolio import Portfolio
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.reports import DividendIncomeReport, PerformanceReport, ProjectionReport
from app.services.reports_service import (
    get_dividend_income_report,
    get_performance_report,
    get_projection_report,
)

router = APIRouter(prefix="/reports", tags=["Relatórios"])


async def _get_owned_portfolio(
    portfolio_id: int, db: AsyncSession, current_user: User
) -> Portfolio:
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada.",
        )
    return portfolio


@router.get(
    "/performance",
    response_model=PerformanceReport,
    summary="Relatório de performance da carteira",
)
async def performance(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PerformanceReport:
    """Retorno total (R$ e %) por carteira e por posição individual."""
    portfolio = await _get_owned_portfolio(portfolio_id, db, current_user)
    return await get_performance_report(db, portfolio)


@router.get(
    "/dividend-income",
    response_model=DividendIncomeReport,
    summary="Renda mensal de proventos (últimos 12 meses)",
)
async def dividend_income(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DividendIncomeReport:
    """Agrupa dividendos dos ativos da carteira por mês nos últimos 12 meses."""
    portfolio = await _get_owned_portfolio(portfolio_id, db, current_user)
    return await get_dividend_income_report(db, portfolio)


@router.get(
    "/projections",
    response_model=ProjectionReport,
    summary="Projeção de renda passiva anual/mensal",
)
async def projections(
    portfolio_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectionReport:
    """Projeta renda passiva anual e mensal com base nos dividendos dos últimos 12 meses."""
    portfolio = await _get_owned_portfolio(portfolio_id, db, current_user)
    return await get_projection_report(db, portfolio)
