"""Serviço de resolução de ativos por ticker com criação e enriquecimento automáticos."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset

logger = logging.getLogger(__name__)


def _infer_asset_type(ticker: str) -> str:
    """FII = ticker termina com 11; demais são ACAO."""
    return "FII" if ticker.upper().endswith("11") else "ACAO"


async def enrich_asset(db: AsyncSession, asset: Asset) -> Asset:
    """Tenta enriquecer o ativo com dados externos (nome, setor, tipo).

    Executado apenas quando o nome ainda é o placeholder (igual ao ticker).
    Falhas de enriquecimento são silenciosas para não bloquear a transação.
    """
    if asset.name != asset.ticker:
        return asset

    try:
        from app.integrations.market_data.aggregator import market_data_aggregator

        info = await market_data_aggregator.get_asset_info(asset.ticker)
        if info is None:
            return asset

        asset.name = info.name
        if info.sector:
            asset.sector = info.sector
        asset.asset_type = info.asset_type
        await db.flush()
    except Exception as exc:
        logger.warning("[asset_service] Enriquecimento falhou para '%s': %s", asset.ticker, exc)

    return asset


async def get_or_create_asset(db: AsyncSession, ticker: str) -> Asset:
    """Retorna ativo existente ou cria novo, enriquecendo com dados externos."""
    ticker = ticker.strip().upper()
    result = await db.execute(select(Asset).where(Asset.ticker == ticker))
    asset = result.scalar_one_or_none()

    if asset is not None:
        return await enrich_asset(db, asset)

    asset = Asset(
        ticker=ticker,
        name=ticker,
        sector=None,
        asset_type=_infer_asset_type(ticker),
        is_active=True,
    )
    db.add(asset)
    await db.flush()
    return await enrich_asset(db, asset)
