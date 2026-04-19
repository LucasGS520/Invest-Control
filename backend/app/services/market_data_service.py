"""Adapter de dados de mercado preservando a API publica existente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.integrations.market_data import market_data_aggregator
from app.integrations.market_data.providers.brapi_provider import BrapiProvider

_BRAPI_PROVIDER = BrapiProvider()


async def fetch_quote_from_api(ticker: str) -> dict:
    """Busca cotacao diretamente no provider externo para o fluxo de refresh."""

    quote = await _BRAPI_PROVIDER.get_quote(ticker)
    return {
        "ticker": quote.ticker,
        "price": quote.price,
        "change_percent": quote.change_percent,
        "volume": quote.volume,
    }


async def get_quote(db: AsyncSession, ticker: str) -> MarketQuote:
    """Retorna cotacao usando cache local e fallback configuravel por provider."""

    return await market_data_aggregator.get_quote(db, ticker)


async def get_quotes(db: AsyncSession, tickers: list[str]) -> dict[str, MarketQuote]:
    """Retorna cotacoes em lote mantendo persistencia compatível."""

    return await market_data_aggregator.get_quotes(db, tickers)


async def fetch_dividends_from_api(ticker: str) -> list[dict]:
    """Busca dividendos diretamente no provider externo para compatibilidade."""

    items = await _BRAPI_PROVIDER.get_dividends(ticker)
    return [
        {
            "value": item.value,
            "ex_date": item.ex_date,
            "payment_date": item.payment_date,
            "dividend_type": item.dividend_type,
        }
        for item in items
    ]


async def sync_dividends(db: AsyncSession, ticker: str) -> list[Dividend]:
    """Sincroniza dividendos via agregador mantendo a assinatura existente."""

    return await market_data_aggregator.sync_dividends(db, ticker)


async def enrich_asset_metadata(db: AsyncSession, ticker: str) -> None:
    """Busca metadados externos e atualiza o registro do ativo se necessário."""
    from sqlalchemy import select

    from app.db.models.asset import Asset
    from app.services.asset_service import enrich_asset

    result = await db.execute(select(Asset).where(Asset.ticker == ticker.upper()))
    asset = result.scalar_one_or_none()
    if asset is not None:
        await enrich_asset(db, asset)


async def get_dividends(db: AsyncSession, ticker: str) -> list[Dividend]:
    """Retorna proventos persistidos, sincronizando se necessario."""

    ticker = ticker.upper()
    result = await db.execute(
        select(Dividend)
        .where(Dividend.ticker == ticker)
        .order_by(Dividend.ex_date.desc())
    )
    dividends = list(result.scalars().all())

    if not dividends:
        await sync_dividends(db, ticker)
        result = await db.execute(
            select(Dividend)
            .where(Dividend.ticker == ticker)
            .order_by(Dividend.ex_date.desc())
        )
        dividends = list(result.scalars().all())

    return dividends
