"""Provider de cotacoes via Twelve Data HTTP API."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx

from app.core.config import settings
from app.integrations.market_data.base import BasePriceProvider, Quote


class TwelveDataProvider(BasePriceProvider):
    """Provider com suporte a chamada simples e em lote tolerante a payloads."""

    provider_name = "twelvedata"

    async def get_quote(self, ticker: str) -> Quote:
        payload = await self._request("quote", {"symbol": ticker.upper()})
        return self._build_quote(ticker.upper(), payload)

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        symbols = [ticker.upper() for ticker in tickers]
        if not symbols:
            return {}

        payload = await self._request("quote", {"symbol": ",".join(symbols)})
        raw_items = self._extract_batch_payload(payload, symbols)
        quotes: dict[str, Quote] = {}
        missing: list[str] = []

        for symbol in symbols:
            item = raw_items.get(symbol)
            if not item:
                missing.append(symbol)
                continue
            quotes[symbol] = self._build_quote(symbol, item)

        if missing:
            fallback_items = await asyncio.gather(*(self.get_quote(symbol) for symbol in missing), return_exceptions=True)
            for item in fallback_items:
                if isinstance(item, Quote):
                    quotes[item.ticker] = item

        return quotes

    async def _request(self, endpoint: str, params: dict[str, str]) -> dict:
        if not settings.twelvedata_api_key:
            raise ValueError("TWELVEDATA_API_KEY nao configurada.")

        merged_params = {**params, "apikey": settings.twelvedata_api_key}
        url = f"{settings.twelvedata_base_url.rstrip('/')}/{endpoint}"
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=merged_params)
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, dict) and payload.get("status") == "error":
                        raise ValueError(payload.get("message", "Erro ao consultar Twelve Data."))
                    return payload
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt == 2:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))

        raise ValueError(f"Falha ao consultar Twelve Data: {last_error}")

    def _extract_batch_payload(self, payload: dict, symbols: list[str]) -> dict[str, dict]:
        if all(symbol in payload for symbol in symbols):
            return {symbol: payload[symbol] for symbol in symbols if isinstance(payload.get(symbol), dict)}

        values = payload.get("data") or payload.get("values") or payload.get("result")
        if isinstance(values, list):
            result: dict[str, dict] = {}
            for item in values:
                symbol = (item.get("symbol") or "").upper()
                if symbol:
                    result[symbol] = item
            return result

        if isinstance(values, dict):
            return {symbol.upper(): item for symbol, item in values.items() if isinstance(item, dict)}

        return {}

    def _build_quote(self, ticker: str, payload: dict) -> Quote:
        price = payload.get("close") or payload.get("price")
        if price is None:
            raise ValueError(f"Cotacao indisponivel no Twelve Data para '{ticker}'.")

        return Quote(
            ticker=ticker,
            price=Decimal(str(price)),
            change_percent=_to_decimal(payload.get("percent_change")),
            volume=_to_decimal(payload.get("volume")),
            source=self.provider_name,
        )


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
