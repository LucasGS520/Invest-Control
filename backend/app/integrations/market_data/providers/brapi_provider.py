"""Provider brapi para compatibilidade com a integracao atual."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import httpx

from app.core.config import settings
from app.integrations.market_data.base import AssetInfo, BaseAssetInfoProvider, BaseDividendProvider, BasePriceProvider, DividendItem, Quote

_BRAPI_BASE = "https://brapi.dev/api"


def _normalize_dividend_type(label: str) -> str:
    normalized = label.upper()
    if "JCP" in normalized or "JUROS" in normalized:
        return "JCP"
    if "AMORT" in normalized:
        return "AMORTIZACAO"
    if "REND" in normalized:
        return "RENDIMENTO"
    return "DIVIDENDO"


class BrapiProvider(BasePriceProvider, BaseDividendProvider, BaseAssetInfoProvider):
    """Reaproveita a semantica atual da brapi como provider plugavel."""

    provider_name = "brapi"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if settings.brapi_token:
            headers["Authorization"] = f"Bearer {settings.brapi_token}"
        return headers

    async def get_quote(self, ticker: str) -> Quote:
        url = f"{_BRAPI_BASE}/quote/{ticker.upper()}"
        payload = await self._request_json(url, headers=self._headers())
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"Ticker '{ticker}' nao encontrado na brapi.")

        item = results[0]
        return Quote(
            ticker=item.get("symbol", ticker),
            price=Decimal(str(item.get("regularMarketPrice", 0))),
            change_percent=_to_decimal(item.get("regularMarketChangePercent")),
            volume=_to_decimal(item.get("regularMarketVolume")),
            source=self.provider_name,
        )

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        if not tickers:
            return {}

        url = f"{_BRAPI_BASE}/quote/{','.join(t.upper() for t in tickers)}"
        payload = await self._request_json(url, headers=self._headers())
        quotes: dict[str, Quote] = {}
        for item in payload.get("results", []):
            quote = Quote(
                ticker=item.get("symbol", ""),
                price=Decimal(str(item.get("regularMarketPrice", 0))),
                change_percent=_to_decimal(item.get("regularMarketChangePercent")),
                volume=_to_decimal(item.get("regularMarketVolume")),
                source=self.provider_name,
            )
            quotes[quote.ticker] = quote
        return quotes

    async def get_dividends(self, ticker: str) -> list[DividendItem]:
        url = f"{_BRAPI_BASE}/quote/{ticker.upper()}"
        params = {"fundamental": "false", "dividends": "true"}
        payload = await self._request_json(url, params=params, headers=self._headers())
        results = payload.get("results", [])
        if not results:
            return []

        items: list[DividendItem] = []
        raw_dividends = results[0].get("dividendsData", {}).get("cashDividends", [])
        for raw in raw_dividends:
            ex_date = _parse_iso_date(raw.get("lastDatePrior") or raw.get("ex_date"))
            if ex_date is None:
                continue
            items.append(
                DividendItem(
                    ticker=ticker,
                    value=Decimal(str(raw.get("rate", 0))),
                    ex_date=ex_date,
                    payment_date=_parse_iso_date(raw.get("paymentDate") or raw.get("payment_date")),
                    dividend_type=_normalize_dividend_type(raw.get("label", "DIVIDENDO")),
                    source=self.provider_name,
                )
            )
        return items

    async def get_asset_info(self, ticker: str) -> AssetInfo:
        url = f"{_BRAPI_BASE}/quote/{ticker.upper()}"
        payload = await self._request_json(url, headers=self._headers())
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"Ticker '{ticker}' nao encontrado na brapi.")
        item = results[0]
        ticker_str = (item.get("symbol") or ticker).upper()
        name = item.get("longName") or item.get("shortName") or ticker_str
        asset_type = "FII" if ticker_str.endswith("11") else "ACAO"
        return AssetInfo(
            ticker=ticker_str,
            name=name,
            sector=item.get("sector"),
            asset_type=asset_type,
            source=self.provider_name,
        )

    async def _request_json(self, url: str, **kwargs) -> dict:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt == 2:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))
        raise ValueError(f"Falha ao consultar brapi: {last_error}")


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
