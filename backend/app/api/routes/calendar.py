"""Endpoints de Calendário de Proventos (FR5).

GET /api/calendar/dividends           — próximos ex-dates da carteira do usuário
GET /api/calendar/dividends/{ticker}  — histórico e próximos proventos de um ativo
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.models.asset import Asset
from app.db.models.dividend import Dividend
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.calendar import DividendEventOut, PortfolioCalendarOut, TickerCalendarOut

router = APIRouter(prefix="/calendar", tags=["Calendário"])

# Janela padrão: próximos 90 dias e últimos 180 dias
_UPCOMING_DAYS = 90
_PAST_DAYS = 180


@router.get(
    "/dividends",
    response_model=PortfolioCalendarOut,
    summary="Calendário de proventos da carteira",
)
async def portfolio_calendar(
    portfolio_id: int = Query(..., description="ID da carteira"),
    upcoming_days: int = Query(default=_UPCOMING_DAYS, ge=1, le=365),
    past_days: int = Query(default=_PAST_DAYS, ge=0, le=730),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioCalendarOut:
    """Retorna eventos de proventos (passados e futuros) dos ativos da carteira."""
    # Verifica ownership
    port_result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.positions).selectinload(PortfolioAsset.asset))
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id)
    )
    portfolio = port_result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carteira não encontrada.")

    tickers = [pos.asset.ticker for pos in portfolio.positions if pos.quantity > 0]
    asset_names: dict[str, str] = {
        pos.asset.ticker: pos.asset.name for pos in portfolio.positions
    }

    today = date.today()
    upcoming_cutoff = today + timedelta(days=upcoming_days)
    past_cutoff = today - timedelta(days=past_days)

    if not tickers:
        return PortfolioCalendarOut(
            portfolio_id=portfolio_id,
            upcoming_events=[],
            past_events=[],
        )

    div_result = await db.execute(
        select(Dividend).where(
            Dividend.ticker.in_(tickers),
            Dividend.ex_date >= past_cutoff,
            Dividend.ex_date <= upcoming_cutoff,
        ).order_by(Dividend.ex_date)
    )
    dividends = div_result.scalars().all()

    upcoming: list[DividendEventOut] = []
    past: list[DividendEventOut] = []

    for d in dividends:
        event = DividendEventOut(
            ticker=d.ticker,
            asset_name=asset_names.get(d.ticker),
            value=d.value,
            ex_date=d.ex_date,
            payment_date=d.payment_date,
            dividend_type=d.dividend_type,
        )
        if d.ex_date >= today:
            upcoming.append(event)
        else:
            past.append(event)

    # Futuros: mais próximos primeiro; Passados: mais recentes primeiro
    upcoming.sort(key=lambda e: e.ex_date)
    past.sort(key=lambda e: e.ex_date, reverse=True)

    return PortfolioCalendarOut(
        portfolio_id=portfolio_id,
        upcoming_events=upcoming,
        past_events=past,
    )


@router.get(
    "/dividends/{ticker}",
    response_model=TickerCalendarOut,
    summary="Histórico e próximos proventos de um ativo",
)
async def ticker_calendar(
    ticker: str,
    upcoming_days: int = Query(default=_UPCOMING_DAYS, ge=1, le=365),
    past_days: int = Query(default=_PAST_DAYS, ge=0, le=730),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TickerCalendarOut:
    """Retorna histórico e eventos futuros de proventos para um ticker específico."""
    ticker = ticker.upper()

    # Verifica se o ativo existe
    asset_result = await db.execute(select(Asset.name).where(Asset.ticker == ticker))
    asset_name = asset_result.scalar_one_or_none()

    today = date.today()
    upcoming_cutoff = today + timedelta(days=upcoming_days)
    past_cutoff = today - timedelta(days=past_days)

    div_result = await db.execute(
        select(Dividend).where(
            Dividend.ticker == ticker,
            Dividend.ex_date >= past_cutoff,
            Dividend.ex_date <= upcoming_cutoff,
        ).order_by(Dividend.ex_date)
    )
    dividends = div_result.scalars().all()

    upcoming: list[DividendEventOut] = []
    past: list[DividendEventOut] = []

    for d in dividends:
        event = DividendEventOut(
            ticker=d.ticker,
            asset_name=asset_name,
            value=d.value,
            ex_date=d.ex_date,
            payment_date=d.payment_date,
            dividend_type=d.dividend_type,
        )
        if d.ex_date >= today:
            upcoming.append(event)
        else:
            past.append(event)

    past.sort(key=lambda e: e.ex_date, reverse=True)

    return TickerCalendarOut(
        ticker=ticker,
        upcoming_events=upcoming,
        past_events=past,
    )
