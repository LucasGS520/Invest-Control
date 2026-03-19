"""Endpoints CRUD para carteiras de investimento."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.portfolio import Portfolio
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.portfolio import PortfolioCreate, PortfolioOut, PortfolioSummary, PortfolioUpdate
from app.services.portfolio_service import get_portfolio_summary

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


async def _get_user_portfolio(portfolio_id: int, user: User, db: AsyncSession) -> Portfolio:
    """Helper: busca carteira por id e valida que pertence ao usuário atual."""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carteira não encontrada.")
    return portfolio


@router.get("/", response_model=list[PortfolioOut], summary="Lista carteiras do usuário")
async def list_portfolios(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Portfolio]:
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=PortfolioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria nova carteira",
)
async def create_portfolio(
    data: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Portfolio:
    portfolio = Portfolio(user_id=user.id, name=data.name, description=data.description)
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioSummary, summary="Detalha carteira com posições")
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortfolioSummary:
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    return await get_portfolio_summary(db, portfolio)


@router.patch("/{portfolio_id}", response_model=PortfolioOut, summary="Atualiza dados da carteira")
async def update_portfolio(
    portfolio_id: int,
    data: PortfolioUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Portfolio:
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    if data.name is not None:
        portfolio.name = data.name
    if data.description is not None:
        portfolio.description = data.description
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove carteira")
async def delete_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    await db.delete(portfolio)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
