from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.market_data.providers.brapi_provider import BrapiProvider
from app.integrations.market_data.providers.fundamentus_provider import FundamentusProvider
from app.integrations.market_data.providers.statusinvest_provider import StatusInvestProvider
from app.integrations.market_data.providers.twelvedata_provider import TwelveDataProvider
from app.integrations.market_data.providers.yfinance_provider import YFinanceProvider


def _mock_http_response(payload: dict) -> AsyncMock:
    response = AsyncMock()
    response.json.return_value = payload
    response.raise_for_status = lambda: None
    return response


@pytest.mark.asyncio
async def test_brapi_provider_get_quote_maps_payload():
    provider = BrapiProvider(timeout_seconds=1)
    payload = {
        "results": [
            {
                "symbol": "MXRF11",
                "regularMarketPrice": 10.5,
                "regularMarketChangePercent": -0.5,
                "regularMarketVolume": 1500000,
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=_mock_http_response(payload)):
        quote = await provider.get_quote("mxrf11")

    assert quote.ticker == "MXRF11"
    assert quote.price == Decimal("10.5")
    assert quote.change_percent == Decimal("-0.5")
    assert quote.volume == Decimal("1500000")
    assert quote.source == "brapi"


@pytest.mark.asyncio
async def test_brapi_provider_get_dividends_normalizes_items():
    provider = BrapiProvider(timeout_seconds=1)
    payload = {
        "results": [
            {
                "dividendsData": {
                    "cashDividends": [
                        {
                            "rate": 0.1,
                            "lastDatePrior": "2025-04-01T00:00:00.000Z",
                            "paymentDate": "2025-04-15T00:00:00.000Z",
                            "label": "Rendimento",
                        }
                    ]
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=_mock_http_response(payload)):
        dividends = await provider.get_dividends("mxrf11")

    assert len(dividends) == 1
    assert dividends[0].ticker == "MXRF11"
    assert dividends[0].value == Decimal("0.1")
    assert dividends[0].ex_date == date(2025, 4, 1)
    assert dividends[0].payment_date == date(2025, 4, 15)
    assert dividends[0].dividend_type == "RENDIMENTO"


@pytest.mark.asyncio
async def test_twelvedata_provider_batch_falls_back_to_single_quotes():
    provider = TwelveDataProvider(timeout_seconds=1)

    with (
        patch.object(
            provider,
            "_request",
            AsyncMock(return_value={"PETR4": {"symbol": "PETR4", "price": "32.10"}}),
        ),
        patch.object(
            provider,
            "get_quote",
            AsyncMock(
                side_effect=[
                    provider._build_quote("VALE3", {"price": "55.40", "percent_change": "1.2"}),
                ]
            ),
        ) as get_quote_mock,
    ):
        quotes = await provider.get_quotes(["PETR4", "VALE3"])

    assert set(quotes) == {"PETR4", "VALE3"}
    assert quotes["PETR4"].price == Decimal("32.10")
    assert quotes["VALE3"].price == Decimal("55.40")
    get_quote_mock.assert_awaited_once_with("VALE3")


@pytest.mark.asyncio
async def test_yfinance_provider_get_quote_uses_retry():
    provider = YFinanceProvider(timeout_seconds=1)

    with patch(
        "app.integrations.market_data.providers.yfinance_provider.asyncio.to_thread",
        AsyncMock(side_effect=[RuntimeError("boom"), {"lastPrice": 15.5, "lastVolume": 1200}]),
    ):
        quote = await provider.get_quote("hglg11")

    assert quote.ticker == "HGLG11"
    assert quote.price == Decimal("15.5")
    assert quote.volume == Decimal("1200")


def test_statusinvest_provider_parses_dividend_table():
    provider = StatusInvestProvider(timeout_seconds=1)
    html = """
    <table>
      <tbody>
        <tr>
          <td>Rendimento</td>
          <td>01/04/2025</td>
          <td>15/04/2025</td>
          <td>R$ 0,12</td>
        </tr>
      </tbody>
    </table>
    """

    dividends = provider._parse_dividends("MXRF11", html)

    assert len(dividends) == 1
    assert dividends[0].ticker == "MXRF11"
    assert dividends[0].value == Decimal("0.12")
    assert dividends[0].ex_date == date(2025, 4, 1)
    assert dividends[0].payment_date == date(2025, 4, 15)
    assert dividends[0].dividend_type == "RENDIMENTO"


def test_fundamentus_provider_parses_dividend_table():
    provider = FundamentusProvider(timeout_seconds=1)
    html = """
    <table>
      <tr>
        <td>02/05/2025</td>
        <td>20/05/2025</td>
        <td>JCP</td>
        <td>R$ 1,25</td>
      </tr>
    </table>
    """

    dividends = provider._parse_dividends("ITUB4", html)

    assert len(dividends) == 1
    assert dividends[0].ticker == "ITUB4"
    assert dividends[0].value == Decimal("1.25")
    assert dividends[0].ex_date == date(2025, 5, 2)
    assert dividends[0].payment_date == date(2025, 5, 20)
    assert dividends[0].dividend_type == "JCP"
