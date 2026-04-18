"""Provider de dividendos/fundamentos via scraping do Fundamentus."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.integrations.market_data.base import BaseDividendProvider, DividendItem

_USER_AGENT = "Mozilla/5.0 (compatible; InvestControlBot/1.0; +https://example.invalid)"


class FundamentusProvider(BaseDividendProvider):
    """Fallback para proventos quando outras fontes nao responderem bem."""

    provider_name = "fundamentus"
    base_url = "https://www.fundamentus.com.br"

    async def get_dividends(self, ticker: str) -> list[DividendItem]:
        url = f"{self.base_url}/proventos.php?papel={ticker.upper()}"
        html = await self._fetch_html(url)
        return self._parse_dividends(ticker.upper(), html)

    async def _fetch_html(self, url: str) -> str:
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def _parse_dividends(self, ticker: str, html: str) -> list[DividendItem]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("table tr")
        dividends: list[DividendItem] = []

        for row in rows:
            columns = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(columns) < 3:
                continue

            ex_date = _parse_br_date(_find_date(columns, 0))
            amount = _parse_decimal(_find_amount(columns))
            if ex_date is None or amount is None:
                continue

            payment_date = _parse_br_date(_find_date(columns, 1))
            dividends.append(
                DividendItem(
                    ticker=ticker,
                    value=amount,
                    ex_date=ex_date,
                    payment_date=payment_date,
                    dividend_type=_infer_dividend_type(columns),
                    source=self.provider_name,
                )
            )

        return dividends


def _find_date(columns: list[str], index: int) -> str | None:
    dates = [item for item in columns if item.count("/") == 2]
    return dates[index] if len(dates) > index else None


def _find_amount(columns: list[str]) -> str | None:
    for item in columns:
        if "," in item or "R$" in item:
            return item
    return None


def _parse_br_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    normalized = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(normalized)
    except Exception:
        return None


def _infer_dividend_type(columns: list[str]) -> str:
    joined = " ".join(columns).upper()
    if "JCP" in joined or "JUROS" in joined:
        return "JCP"
    if "REND" in joined:
        return "RENDIMENTO"
    if "AMORT" in joined:
        return "AMORTIZACAO"
    return "DIVIDENDO"
