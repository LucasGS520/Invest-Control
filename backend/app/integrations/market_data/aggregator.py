"""Agregador principal para cotacoes e dividendos de mercado."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.integrations.market_data.base import AssetInfo, BaseAssetInfoProvider, BaseDividendProvider, BasePriceProvider, DividendItem, PermanentError, Quote, TransientError
from app.integrations.market_data.metrics import market_metrics
from app.integrations.market_data.ticker_resolver import resolve_for_provider, to_canonical
from app.integrations.market_data.providers import (
    BrapiProvider,
    FundamentusProvider,
    StatusInvestProvider,
    TwelveDataProvider,
    YFinanceProvider,
)


class _CircuitBreaker:
    """Abre o circuito de um provider após falhas consecutivas."""

    def __init__(self, threshold: int = 3, reset_seconds: float = 60.0) -> None:
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, datetime] = {}
        self._threshold = threshold
        self._reset_seconds = reset_seconds

    def is_open(self, name: str) -> bool:
        until = self._open_until.get(name)
        if until is None:
            return False
        if datetime.now(timezone.utc) >= until:
            self._failures[name] = 0
            del self._open_until[name]
            return False
        return True

    def record_failure(self, name: str) -> None:
        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        if count >= self._threshold:
            until = datetime.now(timezone.utc) + timedelta(seconds=self._reset_seconds)
            self._open_until[name] = until
            market_metrics.record_circuit_breaker_open(name)
            logger.warning(
                "circuit_breaker_open provider=%s failures=%d reset_at=%s",
                name, count, until.isoformat(),
            )
        else:
            logger.debug("circuit_breaker_failure provider=%s failures=%d threshold=%d", name, count, self._threshold)

    def record_success(self, name: str) -> None:
        was_open = name in self._open_until
        self._failures[name] = 0
        self._open_until.pop(name, None)
        if was_open:
            logger.info("circuit_breaker_closed provider=%s", name)


class MarketDataAggregator:
    """Orquestra fallback entre providers e persistencia local."""

    def __init__(self) -> None:
        self._price_providers = self._build_price_providers()
        self._dividend_providers = self._build_dividend_providers()
        self._semaphore = asyncio.Semaphore(max(settings.market_data_concurrency, 1))
        self._circuit_breaker = _CircuitBreaker(
            threshold=settings.circuit_breaker_threshold,
            reset_seconds=settings.circuit_breaker_reset_seconds,
        )

    async def get_quote(self, db: AsyncSession, ticker: str) -> MarketQuote:
        ticker = to_canonical(ticker)
        cached = await self._get_cached_quote(db, ticker)
        if cached is not None:
            market_metrics.record_cache_hit()
            logger.debug("cache_hit ticker=%s source=%s", ticker, cached.source)
            return cached

        market_metrics.record_cache_miss()
        logger.debug("cache_miss ticker=%s", ticker)
        quote = await self._fetch_quote_with_fallback(ticker)
        return await self._persist_quote(db, quote)

    async def get_quotes(self, db: AsyncSession, tickers: list[str]) -> dict[str, MarketQuote]:
        normalized = list(dict.fromkeys(to_canonical(ticker) for ticker in tickers if ticker))
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

    async def get_asset_info(self, ticker: str) -> AssetInfo | None:
        """Busca metadados do ativo com fallback entre providers."""
        ticker = to_canonical(ticker)
        for name, provider in self._price_providers.items():
            if not isinstance(provider, BaseAssetInfoProvider):
                continue
            if self._circuit_breaker.is_open(name):
                continue
            try:
                async with self._semaphore:
                    info = await provider.get_asset_info(ticker)
                self._circuit_breaker.record_success(name)
                return info
            except Exception:
                self._circuit_breaker.record_failure(name)
        return None

    async def sync_dividends(self, db: AsyncSession, ticker: str) -> list[Dividend]:
        ticker = to_canonical(ticker)
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

    @staticmethod
    def _cache_ttl_minutes(ticker: str) -> int:
        """Retorna TTL de cache em minutos baseado no tipo de ativo detectado pelo ticker."""
        sla = settings.asset_type_sla_minutes
        if ticker.endswith("11"):
            return sla.get("FII", sla.get("ETF", settings.market_data_cache_minutes))
        return sla.get("ACAO", settings.market_data_cache_minutes)

    async def _get_cached_quote(self, db: AsyncSession, ticker: str) -> MarketQuote | None:
        result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == ticker))
        cached = result.scalar_one_or_none()
        if cached is None:
            return None

        cache_limit = datetime.now(timezone.utc) - timedelta(minutes=self._cache_ttl_minutes(ticker))
        updated = cached.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return cached if updated >= cache_limit else None

    async def _get_cached_quotes(self, db: AsyncSession, tickers: list[str]) -> dict[str, MarketQuote]:
        result = await db.execute(select(MarketQuote).where(MarketQuote.ticker.in_(tickers)))
        now = datetime.now(timezone.utc)

        cached_map: dict[str, MarketQuote] = {}
        for row in result.scalars().all():
            updated = row.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            cache_limit = now - timedelta(minutes=self._cache_ttl_minutes(row.ticker))
            if updated >= cache_limit:
                cached_map[row.ticker] = row
        return cached_map

    async def _fetch_quote_with_fallback(self, ticker: str) -> Quote:
        last_error: Exception | None = None
        attempt = 0
        for name, provider in self._price_providers.items():
            if self._circuit_breaker.is_open(name):
                logger.debug("provider_skipped ticker=%s provider=%s reason=circuit_open", ticker, name)
                continue
            if attempt > 0:
                market_metrics.record_fallback()
            attempt += 1
            provider_ticker = resolve_for_provider(ticker, name)
            try:
                async with self._semaphore:
                    result = await provider.get_quote(provider_ticker)
                self._circuit_breaker.record_success(name)
                result = result.model_copy(update={"ticker": ticker})
                logger.info("quote_fetched ticker=%s provider=%s price=%s", ticker, name, result.price)
                return result
            except PermanentError as exc:
                last_error = exc
                logger.info("provider_permanent_error ticker=%s provider=%s error=%s", ticker, name, exc)
            except Exception as exc:
                last_error = exc
                market_metrics.record_quote_error(name)
                self._circuit_breaker.record_failure(name)
                logger.warning("provider_error ticker=%s provider=%s error=%s", ticker, name, exc)
        raise ValueError(f"Falha ao obter cotacao para '{ticker}': {last_error}")

    async def _fetch_quotes_with_fallback(self, tickers: list[str]) -> dict[str, Quote]:
        remaining = list(tickers)
        quotes: dict[str, Quote] = {}
        last_error: Exception | None = None

        for name, provider in self._price_providers.items():
            if not remaining:
                break
            if self._circuit_breaker.is_open(name):
                logger.debug("provider_skipped batch=%s provider=%s reason=circuit_open", remaining, name)
                continue

            provider_tickers = [resolve_for_provider(t, name) for t in remaining]
            try:
                async with self._semaphore:
                    batch = await provider.get_quotes(provider_tickers)
                self._circuit_breaker.record_success(name)
            except PermanentError as exc:
                last_error = exc
                logger.info("provider_permanent_error batch provider=%s error=%s", name, exc)
                batch = {}
            except Exception as exc:
                last_error = exc
                self._circuit_breaker.record_failure(name)
                logger.warning("provider_error batch provider=%s error=%s", name, exc)
                batch = {}

            # Remap provider tickers back to canonical form
            canonical_batch: dict[str, Quote] = {}
            for provider_ticker, quote in batch.items():
                canonical = to_canonical(provider_ticker)
                canonical_batch[canonical] = quote.model_copy(update={"ticker": canonical})

            for ticker in remaining:
                if ticker in canonical_batch:
                    quotes[ticker] = canonical_batch[ticker]

            current_remaining = [ticker for ticker in remaining if ticker not in quotes]
            if current_remaining:
                single_batch = await self._fetch_quotes_individually(provider, current_remaining, name)
                quotes.update(single_batch)
            remaining = [ticker for ticker in remaining if ticker not in quotes]

        if remaining and not quotes:
            raise ValueError(f"Falha ao obter cotacoes para {remaining}: {last_error}")
        return quotes

    async def _fetch_dividends_with_fallback(self, ticker: str) -> list[DividendItem]:
        last_error: Exception | None = None
        for name, provider in self._dividend_providers.items():
            if self._circuit_breaker.is_open(name):
                logger.debug("provider_skipped ticker=%s provider=%s reason=circuit_open", ticker, name)
                continue
            provider_ticker = resolve_for_provider(ticker, name)
            try:
                async with self._semaphore:
                    items = await provider.get_dividends(provider_ticker)
                if items:
                    normalized = [item.model_copy(update={"ticker": ticker}) for item in items]
                    self._circuit_breaker.record_success(name)
                    logger.info("dividends_fetched ticker=%s provider=%s count=%d", ticker, name, len(normalized))
                    return normalized
                logger.debug("dividends_empty ticker=%s provider=%s", ticker, name)
            except PermanentError as exc:
                last_error = exc
                logger.info("provider_permanent_error ticker=%s provider=%s error=%s", ticker, name, exc)
            except Exception as exc:
                last_error = exc
                self._circuit_breaker.record_failure(name)
                logger.warning("provider_error ticker=%s provider=%s error=%s", ticker, name, exc)
        if last_error is not None:
            raise ValueError(f"Falha ao obter dividendos para '{ticker}': {last_error}")
        return []

    async def _fetch_quotes_individually(
        self,
        provider: BasePriceProvider,
        tickers: list[str],
        provider_name: str = "",
    ) -> dict[str, Quote]:
        async def _fetch_one(canonical: str) -> tuple[str, Quote | None]:
            provider_ticker = resolve_for_provider(canonical, provider_name)
            try:
                async with self._semaphore:
                    quote = await provider.get_quote(provider_ticker)
                return canonical, quote.model_copy(update={"ticker": canonical})
            except Exception:
                return canonical, None

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
