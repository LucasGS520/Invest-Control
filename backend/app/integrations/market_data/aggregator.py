"""Agregador principal para cotacoes e dividendos de mercado."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.integrations.market_data.base import BaseDividendProvider, BasePriceProvider, DividendItem, Quote
from app.integrations.market_data.providers import (
    BrapiProvider,
    FundamentusProvider,
    StatusInvestProvider,
    TwelveDataProvider,
    YFinanceProvider,
)


class MarketDataAggregator:
    """Orquestra fallback entre providers e persistencia local."""

    def __init__(self) -> None:
        self._price_providers = self._build_price_providers()
        self._dividend_providers = self._build_dividend_providers()
        self._semaphore = asyncio.Semaphore(max(settings.market_data_concurrency, 1))

    async def get_quote(self, db: AsyncSession, ticker: str) -> MarketQuote:
        ticker = ticker.upper()
        cached = await self._get_cached_quote(db, ticker)
        if cached is not None:
            return cached

        quote = await self._fetch_quote_with_fallback(ticker)
        return await self._persist_quote(db, quote)

    async def get_quotes(self, db: AsyncSession, tickers: list[str]) -> dict[str, MarketQuote]:
        normalized = list(dict.fromkeys(ticker.upper() for ticker in tickers if ticker))
        if not normalized:
            return {}

        cached_map = await self._get_cached_quotes(db, normalized)
        missing = [ticker for ticker in normalized if ticker not in cached_map]
        fresh_quotes: dict[str, Quote] = {}

        if missing:
            fresh_quotes = await self._fetch_quotes_with_fallback(missing)

        persisted: dict[str, MarketQuote] = dict(cached_map)
        for ticker in missing:
            quote = fresh_quotes.get(ticker)
            if quote is None:
                continue
            persisted[ticker] = await self._persist_quote(db, quote, commit=False)

        if fresh_quotes:
            await db.commit()
            for item in fresh_quotes.values():
                await db.refresh(persisted[item.ticker])

        return persisted

    async def sync_dividends(self, db: AsyncSession, ticker: str) -> list[Dividend]:
        ticker = ticker.upper()
        items = await self._fetch_dividends_with_fallback(ticker)

        existing_result = await db.execute(select(Dividend.ex_date).where(Dividend.ticker == ticker))
        existing_ex_dates = {row[0] for row in existing_result.all()}

        new_rows: list[Dividend] = []
        for item in items:
            if item.ex_date in existing_ex_dates:
                continue

            row = Dividend(
                ticker=item.ticker,
                value=item.value,
                ex_date=item.ex_date,
                payment_date=item.payment_date,
                dividend_type=item.dividend_type,
            )
            db.add(row)
            new_rows.append(row)
            existing_ex_dates.add(item.ex_date)

        if new_rows:
            await db.commit()
            for row in new_rows:
                await db.refresh(row)

        return new_rows

    def _build_price_providers(self) -> dict[str, BasePriceProvider]:
        providers: dict[str, BasePriceProvider] = {}
        for name in settings.price_providers_order:
            provider = self._create_price_provider(name)
            if provider is not None:
                providers[name] = provider
        return providers

    def _build_dividend_providers(self) -> dict[str, BaseDividendProvider]:
        providers: dict[str, BaseDividendProvider] = {}
        for name in settings.dividend_providers_order:
            provider = self._create_dividend_provider(name)
            if provider is not None:
                providers[name] = provider
        return providers

    def _create_price_provider(self, name: str) -> BasePriceProvider | None:
        timeout = self._provider_timeout(name)
        factories: dict[str, type[BasePriceProvider]] = {
            "brapi": BrapiProvider,
            "twelvedata": TwelveDataProvider,
            "yfinance": YFinanceProvider,
        }
        provider_cls = factories.get(name)
        return provider_cls(timeout_seconds=timeout) if provider_cls else None

    def _create_dividend_provider(self, name: str) -> BaseDividendProvider | None:
        timeout = self._provider_timeout(name)
        factories: dict[str, type[BaseDividendProvider]] = {
            "brapi": BrapiProvider,
            "statusinvest": StatusInvestProvider,
            "fundamentus": FundamentusProvider,
        }
        provider_cls = factories.get(name)
        return provider_cls(timeout_seconds=timeout) if provider_cls else None

    def _provider_timeout(self, name: str) -> float:
        return settings.provider_timeouts_seconds.get(
            name,
            settings.provider_timeouts_seconds.get("default", 10.0),
        )

    async def _get_cached_quote(self, db: AsyncSession, ticker: str) -> MarketQuote | None:
        result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == ticker))
        cached = result.scalar_one_or_none()
        if cached is None:
            return None

        cache_limit = datetime.now(timezone.utc) - timedelta(minutes=settings.market_data_cache_minutes)
        updated = cached.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return cached if updated >= cache_limit else None

    async def _get_cached_quotes(self, db: AsyncSession, tickers: list[str]) -> dict[str, MarketQuote]:
        result = await db.execute(select(MarketQuote).where(MarketQuote.ticker.in_(tickers)))
        cache_limit = datetime.now(timezone.utc) - timedelta(minutes=settings.market_data_cache_minutes)

        cached_map: dict[str, MarketQuote] = {}
        for row in result.scalars().all():
            updated = row.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated >= cache_limit:
                cached_map[row.ticker] = row
        return cached_map

    async def _fetch_quote_with_fallback(self, ticker: str) -> Quote:
        last_error: Exception | None = None
        for provider in self._price_providers.values():
            try:
                async with self._semaphore:
                    return await provider.get_quote(ticker)
            except Exception as exc:
                last_error = exc
        raise ValueError(f"Falha ao obter cotacao para '{ticker}': {last_error}")

    async def _fetch_quotes_with_fallback(self, tickers: list[str]) -> dict[str, Quote]:
        remaining = list(tickers)
        quotes: dict[str, Quote] = {}
        last_error: Exception | None = None

        for provider in self._price_providers.values():
            if not remaining:
                break

            try:
                async with self._semaphore:
                    batch = await provider.get_quotes(remaining)
            except Exception as exc:
                last_error = exc
                batch = {}

            normalized_batch = {ticker.upper(): quote for ticker, quote in batch.items()}
            for ticker in remaining:
                quote = normalized_batch.get(ticker)
                if quote is not None:
                    quotes[ticker] = quote
            current_remaining = [ticker for ticker in remaining if ticker not in quotes]
            if current_remaining:
                single_batch = await self._fetch_quotes_individually(provider, current_remaining)
                for ticker, quote in single_batch.items():
                    quotes[ticker] = quote
            remaining = [ticker for ticker in current_remaining if ticker not in quotes]

        if remaining and not quotes:
            raise ValueError(f"Falha ao obter cotacoes para {remaining}: {last_error}")
        return quotes

    async def _fetch_dividends_with_fallback(self, ticker: str) -> list[DividendItem]:
        last_error: Exception | None = None
        for provider in self._dividend_providers.values():
            try:
                async with self._semaphore:
                    items = await provider.get_dividends(ticker)
                if items:
                    return items
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise ValueError(f"Falha ao obter dividendos para '{ticker}': {last_error}")
        return []

    async def _fetch_quotes_individually(
        self,
        provider: BasePriceProvider,
        tickers: list[str],
    ) -> dict[str, Quote]:
        async def _fetch_one(ticker: str) -> tuple[str, Quote | None]:
            try:
                async with self._semaphore:
                    return ticker, await provider.get_quote(ticker)
            except Exception:
                return ticker, None

        results = await asyncio.gather(*(_fetch_one(ticker) for ticker in tickers))
        return {ticker: quote for ticker, quote in results if quote is not None}

    async def _persist_quote(
        self,
        db: AsyncSession,
        quote: Quote,
        *,
        commit: bool = True,
    ) -> MarketQuote:
        result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == quote.ticker))
        row = result.scalar_one_or_none()
        if row is None:
            row = MarketQuote(ticker=quote.ticker)
            db.add(row)

        row.price = quote.price
        row.change_percent = quote.change_percent
        row.volume = quote.volume
        row.updated_at = quote.timestamp

        if commit:
            await db.commit()
            await db.refresh(row)

        return row


market_data_aggregator = MarketDataAggregator()
