from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.integrations.market_data.aggregator import MarketDataAggregator
from app.integrations.market_data.base import DividendItem, Quote


class _PriceProviderStub:
    def __init__(self, *, quote_map=None, batch_map=None, error: Exception | None = None):
        self.quote_map = quote_map or {}
        self.batch_map = batch_map
        self.error = error

    async def get_quote(self, ticker: str) -> Quote:
        if self.error:
            raise self.error
        return self.quote_map[ticker]

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        if self.error:
            raise self.error
        if self.batch_map is not None:
            return {ticker: self.batch_map[ticker] for ticker in tickers if ticker in self.batch_map}
        return {ticker: self.quote_map[ticker] for ticker in tickers if ticker in self.quote_map}


class _DividendProviderStub:
    def __init__(self, *, items=None, error: Exception | None = None):
        self.items = items or []
        self.error = error

    async def get_dividends(self, _ticker: str) -> list[DividendItem]:
        if self.error:
            raise self.error
        return self.items


def _quote(ticker: str, price: str) -> Quote:
    return Quote(
        ticker=ticker,
        price=Decimal(price),
        change_percent=Decimal("1.1"),
        volume=Decimal("1000"),
        timestamp=datetime.now(timezone.utc),
        source="stub",
    )


@pytest.mark.asyncio
async def test_aggregator_get_quote_uses_cache(db_session):
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"stub": _PriceProviderStub(error=RuntimeError("should not call"))}

    db_session.add(
        MarketQuote(
            ticker="MXRF11",
            price=Decimal("10.00"),
            change_percent=Decimal("0.5"),
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    quote = await aggregator.get_quote(db_session, "MXRF11")

    assert quote.ticker == "MXRF11"
    assert Decimal(str(quote.price)) == Decimal("10.00")


@pytest.mark.asyncio
async def test_aggregator_get_quote_falls_back_and_persists(db_session):
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {
        "first": _PriceProviderStub(error=RuntimeError("boom")),
        "second": _PriceProviderStub(quote_map={"ITUB4": _quote("ITUB4", "32.10")}),
    }

    quote = await aggregator.get_quote(db_session, "ITUB4")

    assert quote.ticker == "ITUB4"
    assert Decimal(str(quote.price)) == Decimal("32.10")

    persisted = await db_session.get(MarketQuote, quote.id)
    assert persisted is not None
    assert persisted.ticker == "ITUB4"


@pytest.mark.asyncio
async def test_aggregator_get_quotes_uses_batch_then_single_fallback(db_session):
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {
        "stub": _PriceProviderStub(
            quote_map={"VALE3": _quote("VALE3", "55.40")},
            batch_map={"PETR4": _quote("PETR4", "30.00")},
        )
    }

    quotes = await aggregator.get_quotes(db_session, ["PETR4", "VALE3"])

    assert set(quotes) == {"PETR4", "VALE3"}
    assert Decimal(str(quotes["PETR4"].price)) == Decimal("30.00")
    assert Decimal(str(quotes["VALE3"].price)) == Decimal("55.40")


@pytest.mark.asyncio
async def test_aggregator_sync_dividends_persists_without_duplicates(db_session):
    aggregator = MarketDataAggregator()
    aggregator._dividend_providers = {
        "stub": _DividendProviderStub(
            items=[
                DividendItem(
                    ticker="MXRF11",
                    value=Decimal("0.10"),
                    ex_date=date(2025, 4, 1),
                    payment_date=date(2025, 4, 15),
                    dividend_type="RENDIMENTO",
                ),
                DividendItem(
                    ticker="MXRF11",
                    value=Decimal("0.12"),
                    ex_date=date(2025, 5, 1),
                    payment_date=date(2025, 5, 15),
                    dividend_type="RENDIMENTO",
                ),
            ]
        )
    }

    db_session.add(
        Dividend(
            ticker="MXRF11",
            value=Decimal("0.10"),
            ex_date=date(2025, 4, 1),
            payment_date=date(2025, 4, 15),
            dividend_type="RENDIMENTO",
        )
    )
    await db_session.commit()

    created = await aggregator.sync_dividends(db_session, "MXRF11")

    assert len(created) == 1
    assert created[0].ex_date == date(2025, 5, 1)
