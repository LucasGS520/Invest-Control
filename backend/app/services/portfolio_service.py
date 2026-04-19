"""Serviço de carteiras: lógica de negócio para posições e transações."""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.asset import Asset
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.transaction import Transaction
from app.schemas.portfolio import PortfolioSummary, PositionOut
from app.schemas.transaction import TransactionCreate
from app.services.asset_service import get_or_create_asset


async def apply_transaction(
    db: AsyncSession,
    portfolio: Portfolio,
    data: TransactionCreate,
) -> PortfolioAsset:
    """Registra uma transação e atualiza a posição consolidada (PortfolioAsset).

    BUY: recalcula preço médio ponderado e incrementa quantidade.
    SELL: valida estoque suficiente e decrementa quantidade.
    """
    asset = await get_or_create_asset(db, data.ticker)

    # Registra a transação
    tx = Transaction(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type=data.transaction_type,
        quantity=data.quantity,
        price=data.price,
        fees=data.fees,
        date=data.date,
        notes=data.notes,
    )
    db.add(tx)

    # Busca ou cria a posição consolidada
    pos_result = await db.execute(
        select(PortfolioAsset).where(
            PortfolioAsset.portfolio_id == portfolio.id,
            PortfolioAsset.asset_id == asset.id,
        )
    )
    position = pos_result.scalar_one_or_none()

    if position is None:
        if data.transaction_type == "SELL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não há posição existente para vender este ativo.",
            )
        position = PortfolioAsset(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=0,
            avg_price=Decimal("0"),
        )
        db.add(position)

    if data.transaction_type == "BUY":
        old_total = Decimal(position.quantity) * position.avg_price
        new_total = Decimal(data.quantity) * data.price
        new_qty = position.quantity + data.quantity
        position.avg_price = (old_total + new_total) / Decimal(new_qty)
        position.quantity = new_qty

    elif data.transaction_type == "SELL":
        if position.quantity < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantidade insuficiente: disponível {position.quantity}, solicitado {data.quantity}.",
            )
        position.quantity -= data.quantity

    await db.commit()
    await db.refresh(position)
    return position


async def get_portfolio_summary(db: AsyncSession, portfolio: Portfolio) -> PortfolioSummary:
    """Retorna o resumo da carteira com posições e total investido."""
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.positions).selectinload(PortfolioAsset.asset))
        .where(Portfolio.id == portfolio.id)
    )
    loaded = result.scalar_one()

    tickers = [p.asset.ticker for p in loaded.positions if p.quantity > 0]
    quotes: dict[str, MarketQuote] = {}
    if tickers:
        q_result = await db.execute(select(MarketQuote).where(MarketQuote.ticker.in_(tickers)))
        quotes = {row.ticker: row for row in q_result.scalars().all()}

    positions: list[PositionOut] = []
    total_invested = Decimal("0")

    for pos in loaded.positions:
        if pos.quantity > 0:
            avg = Decimal(str(pos.avg_price))
            qty = Decimal(str(pos.quantity))
            invested = qty * avg
            total_invested += invested

            quote = quotes.get(pos.asset.ticker)
            current_price = Decimal(str(quote.price)) if quote else None
            current_value = qty * current_price if current_price is not None else None
            return_pct = (
                ((current_value - invested) / invested * Decimal("100")).quantize(Decimal("0.01"))
                if current_value is not None and invested > 0
                else None
            )
            change_pct = (
                Decimal(str(quote.change_percent)).quantize(Decimal("0.01"))
                if quote and quote.change_percent is not None
                else None
            )

            positions.append(
                PositionOut(
                    id=pos.id,
                    asset_id=pos.asset_id,
                    ticker=pos.asset.ticker,
                    asset_name=pos.asset.name,
                    asset_type=pos.asset.asset_type,
                    quantity=pos.quantity,
                    avg_price=avg,
                    current_price=current_price,
                    current_value=current_value,
                    return_pct=return_pct,
                    change_percent=change_pct,
                )
            )

    return PortfolioSummary(
        id=loaded.id,
        name=loaded.name,
        description=loaded.description,
        objective=loaded.objective,
        currency=loaded.currency,
        created_at=loaded.created_at,
        total_invested=total_invested,
        positions=positions,
    )


async def recalculate_position(db: AsyncSession, portfolio_id: int, asset_id: int) -> None:
    """Recalcula a posição consolidada replaying todas as transações restantes."""
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset_id,
        )
        .order_by(Transaction.date, Transaction.id)
    )
    transactions = list(result.scalars().all())

    pos_result = await db.execute(
        select(PortfolioAsset).where(
            PortfolioAsset.portfolio_id == portfolio_id,
            PortfolioAsset.asset_id == asset_id,
        )
    )
    position = pos_result.scalar_one_or_none()

    if not transactions:
        if position is not None:
            await db.delete(position)
        await db.commit()
        return

    qty = 0
    avg = Decimal("0")
    for tx in transactions:
        price = Decimal(str(tx.price))
        if tx.transaction_type == "BUY":
            new_total = Decimal(qty) * avg + Decimal(tx.quantity) * price
            qty += tx.quantity
            avg = new_total / Decimal(qty)
        elif tx.transaction_type == "SELL":
            qty -= tx.quantity

    if position is None:
        position = PortfolioAsset(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            quantity=qty,
            avg_price=avg,
        )
        db.add(position)
    else:
        position.quantity = qty
        position.avg_price = avg

    await db.commit()

