"""Endpoints para registrar e consultar transações de uma carteira."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.models.portfolio import Portfolio
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.portfolio_service import apply_transaction, recalculate_position

router = APIRouter(tags=["Transactions"])


async def _get_user_portfolio(portfolio_id: int, user: User, db: AsyncSession) -> Portfolio:
    from fastapi import HTTPException

    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada.")
    return portfolio


@router.post(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra transação (compra ou venda)",
)
async def create_transaction(
    portfolio_id: int,
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionOut:
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    await apply_transaction(db, portfolio, data)

    # Retorna a transação recém-criada com join do asset
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.asset))
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.id.desc())
        .limit(1)
    )
    tx = result.scalar_one()
    return TransactionOut(
        id=tx.id,
        portfolio_id=tx.portfolio_id,
        asset_id=tx.asset_id,
        ticker=tx.asset.ticker,
        transaction_type=tx.transaction_type,
        quantity=tx.quantity,
        price=tx.price,
        fees=tx.fees,
        date=tx.date,
        notes=tx.notes,
        created_at=tx.created_at,
    )


@router.get(
    "/portfolios/{portfolio_id}/transactions",
    response_model=list[TransactionOut],
    summary="Lista transações da carteira",
)
async def list_transactions(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TransactionOut]:
    await _get_user_portfolio(portfolio_id, user, db)

    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.asset))
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    )
    txs = result.scalars().all()
    return [
        TransactionOut(
            id=tx.id,
            portfolio_id=tx.portfolio_id,
            asset_id=tx.asset_id,
            ticker=tx.asset.ticker,
            transaction_type=tx.transaction_type,
            quantity=tx.quantity,
            price=tx.price,
            fees=tx.fees,
            date=tx.date,
            notes=tx.notes,
            created_at=tx.created_at,
        )
        for tx in txs
    ]


async def _get_user_transaction(
    portfolio_id: int, transaction_id: int, user: User, db: AsyncSession
) -> Transaction:
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.asset))
        .where(Transaction.id == transaction_id, Transaction.portfolio_id == portfolio.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return tx


@router.delete(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove transação e recalcula posição",
)
async def delete_transaction(
    portfolio_id: int,
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    tx = await _get_user_transaction(portfolio_id, transaction_id, user, db)
    asset_id = tx.asset_id
    await db.delete(tx)
    await db.flush()
    await recalculate_position(db, portfolio_id, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    response_model=TransactionOut,
    summary="Atualiza campos não-financeiros da transação (notes)",
)
async def update_transaction(
    portfolio_id: int,
    transaction_id: int,
    notes: str | None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionOut:
    tx = await _get_user_transaction(portfolio_id, transaction_id, user, db)
    tx.notes = notes
    await db.commit()
    await db.refresh(tx)
    return TransactionOut(
        id=tx.id,
        portfolio_id=tx.portfolio_id,
        asset_id=tx.asset_id,
        ticker=tx.asset.ticker,
        transaction_type=tx.transaction_type,
        quantity=tx.quantity,
        price=tx.price,
        fees=tx.fees,
        date=tx.date,
        notes=tx.notes,
        created_at=tx.created_at,
    )
