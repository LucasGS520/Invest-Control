"""Serviço de carteiras: lógica de negócio para posições e transações."""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.asset import Asset
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.transaction import Transaction
from app.schemas.portfolio import PortfolioSummary, PositionOut
from app.schemas.transaction import TransactionCreate


async def apply_transaction(
    db: AsyncSession,
    portfolio: Portfolio,
    data: TransactionCreate,
) -> PortfolioAsset:
    """Registra uma transação e atualiza a posição consolidada (PortfolioAsset).

    BUY: recalcula preço médio ponderado e incrementa quantidade.
    SELL: valida estoque suficiente e decrementa quantidade.
    """
    # Valida existência do ativo
    asset_result = await db.execute(select(Asset).where(Asset.id == data.asset_id))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado.")

    # Registra a transação
    tx = Transaction(
        portfolio_id=portfolio.id,
        asset_id=data.asset_id,
        transaction_type=data.transaction_type,
        quantity=data.quantity,
        price=data.price,
        date=data.date,
        notes=data.notes,
    )
    db.add(tx)

    # Busca ou cria a posição consolidada
    pos_result = await db.execute(
        select(PortfolioAsset).where(
            PortfolioAsset.portfolio_id == portfolio.id,
            PortfolioAsset.asset_id == data.asset_id,
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
            asset_id=data.asset_id,
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

    positions: list[PositionOut] = []
    total_invested = Decimal("0")

    for pos in loaded.positions:
        if pos.quantity > 0:
            total_invested += Decimal(pos.quantity) * pos.avg_price
            positions.append(
                PositionOut(
                    id=pos.id,
                    asset_id=pos.asset_id,
                    ticker=pos.asset.ticker,
                    asset_name=pos.asset.name,
                    asset_type=pos.asset.asset_type,
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                )
            )

    return PortfolioSummary(
        id=loaded.id,
        name=loaded.name,
        description=loaded.description,
        created_at=loaded.created_at,
        total_invested=total_invested,
        positions=positions,
    )
