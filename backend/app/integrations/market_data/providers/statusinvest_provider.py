"""Provider de dividendos via scraping do Status Invest."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.integrations.market_data.base import BaseDividendProvider, DividendItem

_USER_AGENT = "Mozilla/5.0 (compatible; InvestControlBot/1.0; +https://example.invalid)"


class StatusInvestProvider(BaseDividendProvider):
    """Extrai dividendos de tabelas HTML publicas do Status Invest."""

    provider_name = "statusinvest"
    base_url = "https://statusinvest.com.br"

    async def get_dividends(self, ticker: str) -> list[DividendItem]:
        errors: list[Exception] = []
        paths = ("acoes", "fundos-imobiliarios", "fiagros", "etfs")
        for path in paths:
            url = f"{self.base_url}/{path}/{ticker.lower()}"
            try:
                html = await self._fetch_html(url)
                dividends = self._parse_dividends(ticker.upper(), html)
                if dividends:
                    return dividends
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[-1]
        return []

    async def _fetch_html(self, url: str) -> str:
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def _parse_dividends(self, ticker: str, html: str) -> list[DividendItem]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("table tbody tr")
        dividends: list[DividendItem] = []

        for row in rows:
            columns = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(columns) < 3:
                continue

            ex_date = _parse_br_date(_find_first_date(columns))
            amount = _parse_decimal(_find_amount(columns))
            if ex_date is None or amount is None:
                continue

            payment_date = _parse_br_date(_find_second_date(columns))
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


def _find_first_date(columns: list[str]) -> str | None:
    for item in columns:
        if _looks_like_date(item):
            return item
    return None


def _find_second_date(columns: list[str]) -> str | None:
    found = [item for item in columns if _looks_like_date(item)]
    return found[1] if len(found) > 1 else None


def _find_amount(columns: list[str]) -> str | None:
    for item in columns:
        if "R$" in item or "," in item:
            return item
    return None


def _looks_like_date(value: str) -> bool:
    return value.count("/") == 2


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
