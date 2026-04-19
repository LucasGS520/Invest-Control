from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.integrations.market_data.aggregator import MarketDataAggregator
from app.integrations.market_data.base import DividendItem, PermanentError, Quote, TransientError


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


# ── Ticker resolver integration ───────────────────────────────────────────────


class _RecordingPriceProvider:
    """Stub que registra o ticker recebido para verificar resolucao."""

    provider_name = "yfinance"

    def __init__(self, response_ticker: str, price: str):
        self.received: list[str] = []
        self._response = _quote(response_ticker, price)

    async def get_quote(self, ticker: str) -> Quote:
        self.received.append(ticker)
        return self._response

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        self.received.extend(tickers)
        return {t: self._response for t in tickers}


@pytest.mark.asyncio
async def test_yfinance_provider_recebe_ticker_com_sa_para_ativo_br(db_session):
    """Provider nomeado 'yfinance' deve receber PETR4.SA, nao PETR4."""
    recording = _RecordingPriceProvider("PETR4.SA", "30.00")
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"yfinance": recording}

    await aggregator.get_quote(db_session, "PETR4")

    assert "PETR4.SA" in recording.received


@pytest.mark.asyncio
async def test_yfinance_provider_nao_adiciona_sa_para_ticker_us(db_session):
    """Provider 'yfinance' NAO deve adicionar .SA para ticker americano."""
    recording = _RecordingPriceProvider("AAPL", "150.00")
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"yfinance": recording}

    await aggregator.get_quote(db_session, "AAPL")

    assert "AAPL" in recording.received
    assert "AAPL.SA" not in recording.received


@pytest.mark.asyncio
async def test_cotacao_persiste_com_ticker_canonico(db_session):
    """Quote persistida no cache deve ter ticker canonico (sem .SA)."""
    recording = _RecordingPriceProvider("PETR4.SA", "30.00")
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"yfinance": recording}

    result = await aggregator.get_quote(db_session, "PETR4")

    assert result.ticker == "PETR4"


# ── Error classification ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_permanent_error_nao_aciona_circuit_breaker(db_session):
    """PermanentError (ticker invalido) nao deve contar como falha de provider."""
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {
        "primeiro": _PriceProviderStub(error=PermanentError("ticker invalido")),
        "segundo": _PriceProviderStub(quote_map={"XPTO3": _quote("XPTO3", "10.00")}),
    }

    await aggregator.get_quote(db_session, "XPTO3")

    assert aggregator._circuit_breaker._failures.get("primeiro", 0) == 0


@pytest.mark.asyncio
async def test_transient_error_aciona_circuit_breaker(db_session):
    """TransientError (timeout/5xx) deve registrar falha no circuit breaker."""
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {
        "falho": _PriceProviderStub(error=TransientError("timeout")),
        "backup": _PriceProviderStub(quote_map={"VALE3": _quote("VALE3", "55.00")}),
    }

    await aggregator.get_quote(db_session, "VALE3")

    assert aggregator._circuit_breaker._failures.get("falho", 0) == 1


@pytest.mark.asyncio
async def test_circuit_breaker_abre_e_pula_provider_apos_threshold(db_session):
    """Apos threshold de falhas, circuit breaker abre e provider e pulado."""
    aggregator = MarketDataAggregator()
    aggregator._circuit_breaker._threshold = 2
    stub_falho = _PriceProviderStub(error=RuntimeError("boom"))
    stub_bom = _PriceProviderStub(quote_map={"ITUB4": _quote("ITUB4", "32.00")})
    aggregator._price_providers = {"falho": stub_falho, "bom": stub_bom}

    # Duas chamadas para abrir o circuito
    for _ in range(2):
        try:
            await aggregator.get_quote(db_session, "XPTO3")
        except Exception:
            pass

    assert aggregator._circuit_breaker.is_open("falho")

    # Com circuito aberto, provider falho e pulado — bom deve responder
    result = await aggregator.get_quote(db_session, "ITUB4")
    assert result.ticker == "ITUB4"


# ── SLA cache TTL por tipo de ativo ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_fii_valido_dentro_do_sla_estendido(db_session):
    """FII (ticker terminado em 11) com cache de 20 min deve ser HIT (SLA=30)."""
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"stub": _PriceProviderStub(error=RuntimeError("nao deve chamar"))}

    db_session.add(
        MarketQuote(
            ticker="MXRF11",
            price=Decimal("10.50"),
            change_percent=Decimal("0.0"),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
    )
    await db_session.commit()

    result = await aggregator.get_quote(db_session, "MXRF11")
    assert result.ticker == "MXRF11"


@pytest.mark.asyncio
async def test_cache_acao_expirado_apos_sla_acao(db_session):
    """Acao com cache de 20 min deve ser MISS (SLA ACAO=15) e buscar provider."""
    stub = _PriceProviderStub(quote_map={"PETR4": _quote("PETR4", "38.00")})
    aggregator = MarketDataAggregator()
    aggregator._price_providers = {"stub": stub}

    db_session.add(
        MarketQuote(
            ticker="PETR4",
            price=Decimal("35.00"),
            change_percent=Decimal("0.0"),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
    )
    await db_session.commit()

    result = await aggregator.get_quote(db_session, "PETR4")
    # Provider retornou 38.00 — cache expirado foi ignorado
    assert Decimal(str(result.price)) == Decimal("38.00")
