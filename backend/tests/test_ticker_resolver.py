"""Testes unitarios para politica canonica de ticker (BR/US, por provider)."""

import pytest

from app.integrations.market_data.ticker_resolver import (
    is_br_ticker,
    resolve_for_provider,
    to_canonical,
)


# ── is_br_ticker ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ticker",
    ["PETR4", "VALE3", "ITUB4", "MGLU3", "HGLG11", "BOVA11", "IVVB11", "MXRF11", "KNRE11"],
)
def test_is_br_ticker_positivos(ticker: str):
    assert is_br_ticker(ticker) is True


@pytest.mark.parametrize(
    "ticker",
    ["AAPL", "MSFT", "TSLA", "SPY", "QQQ", "META", "NVDA", "BRK.B"],
)
def test_is_br_ticker_negativos_us(ticker: str):
    assert is_br_ticker(ticker) is False


def test_is_br_ticker_aceita_sufixo_sa():
    """Ticker com .SA deve ser reconhecido como BR apos remocao do sufixo."""
    assert is_br_ticker("PETR4.SA") is True


def test_is_br_ticker_case_insensitive():
    assert is_br_ticker("petr4") is True
    assert is_br_ticker("aapl") is False


# ── to_canonical ──────────────────────────────────────────────────────────────


def test_to_canonical_remove_sufixo_sa():
    assert to_canonical("PETR4.SA") == "PETR4"


def test_to_canonical_uppercase():
    assert to_canonical("petr4") == "PETR4"


def test_to_canonical_strip_espacos():
    assert to_canonical("  VALE3  ") == "VALE3"


def test_to_canonical_ticker_us_inalterado():
    assert to_canonical("aapl") == "AAPL"
    assert to_canonical("BRK.B") == "BRK.B"


def test_to_canonical_idempotente():
    assert to_canonical(to_canonical("PETR4.SA")) == "PETR4"


# ── resolve_for_provider ──────────────────────────────────────────────────────


def test_resolve_yfinance_br_adiciona_sa():
    assert resolve_for_provider("PETR4", "yfinance") == "PETR4.SA"
    assert resolve_for_provider("HGLG11", "yfinance") == "HGLG11.SA"
    assert resolve_for_provider("BOVA11", "yfinance") == "BOVA11.SA"


def test_resolve_yfinance_us_inalterado():
    assert resolve_for_provider("AAPL", "yfinance") == "AAPL"
    assert resolve_for_provider("MSFT", "yfinance") == "MSFT"


def test_resolve_brapi_br_sem_sa():
    assert resolve_for_provider("PETR4", "brapi") == "PETR4"


def test_resolve_outros_providers_inalterado():
    for provider in ("twelvedata", "statusinvest", "fundamentus", "stub"):
        assert resolve_for_provider("PETR4", provider) == "PETR4"


def test_resolve_yfinance_nao_duplica_sa():
    """Entrada canonica ja sem .SA — nao deve gerar PETR4.SA.SA."""
    result = resolve_for_provider("PETR4", "yfinance")
    assert result == "PETR4.SA"
    assert result.count(".SA") == 1
