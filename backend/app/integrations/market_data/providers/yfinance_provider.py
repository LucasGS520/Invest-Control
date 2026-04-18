"""Provider de cotacoes baseado em yfinance."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import yfinance as yf

from app.integrations.market_data.base import BasePriceProvider, Quote


class YFinanceProvider(BasePriceProvider):
    """Executa chamadas sync do yfinance em thread separada."""

    provider_name = "yfinance"

    async def get_quote(self, ticker: str) -> Quote:
        ticker = ticker.upper()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                data = await asyncio.to_thread(self._fetch_single, ticker)
                return self._build_quote(ticker, data)
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
        raise ValueError(f"Falha ao consultar yfinance para '{ticker}': {last_error}")

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        if not tickers:
            return {}
        symbols = [ticker.upper() for ticker in tickers]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                raw_items = await asyncio.to_thread(self._fetch_many, symbols)
                quotes: dict[str, Quote] = {}
                for symbol, data in raw_items.items():
                    if not data:
                        continue
                    quote = self._build_quote(symbol, data)
                    quotes[quote.ticker] = quote
                return quotes
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
        raise ValueError(f"Falha ao consultar yfinance em lote: {last_error}")

    def _fetch_single(self, ticker: str) -> dict:
        info = yf.Ticker(ticker).fast_info
        return dict(info.items()) if hasattr(info, "items") else dict(info)

    def _fetch_many(self, tickers: list[str]) -> dict[str, dict]:
        data: dict[str, dict] = {}
        tickers_client = yf.Tickers(" ".join(tickers))
        for ticker in tickers:
            try:
                info = tickers_client.tickers[ticker].fast_info
                data[ticker] = dict(info.items()) if hasattr(info, "items") else dict(info)
            except Exception:
                data[ticker] = {}
        return data

    def _build_quote(self, ticker: str, data: dict) -> Quote:
        price = data.get("lastPrice") or data.get("regularMarketPrice") or data.get("previousClose")
        if price is None:
            raise ValueError(f"Cotacao indisponivel no yfinance para '{ticker}'.")

        change_percent = data.get("regularMarketChangePercent")
        if change_percent is None and data.get("lastPrice") and data.get("previousClose"):
            previous_close = Decimal(str(data["previousClose"]))
            if previous_close != 0:
                current = Decimal(str(data["lastPrice"]))
                change_percent = ((current - previous_close) / previous_close) * Decimal("100")

        return Quote(
            ticker=ticker,
            price=Decimal(str(price)),
            change_percent=Decimal(str(change_percent)) if change_percent is not None else None,
            volume=Decimal(str(data["lastVolume"])) if data.get("lastVolume") is not None else None,
            source=self.provider_name,
        )
