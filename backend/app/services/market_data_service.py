"""Serviço de integração com dados de mercado (brapi.dev + cache no PostgreSQL).

Fluxo:
1. Tenta retornar dado do cache (MarketQuote) se ainda dentro da janela configurada.
2. Se cache expirado ou ausente, busca na API brapi.dev.
3. Persiste o resultado no banco para servir de cache nas próximas requisições.

Fonte primária: https://brapi.dev  (free tier — sem autenticação necessária para
cotações básicas; token opcional melhora rate limit)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote

# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────

_BRAPI_BASE = "https://brapi.dev/api"
_TIMEOUT = 10.0  # segundos


def _brapi_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if settings.brapi_token:
        headers["Authorization"] = f"Bearer {settings.brapi_token}"
    return headers


# ──────────────────────────────────────────────────────────────────────────────
# Cotações
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_quote_from_api(ticker: str) -> dict:
    """Busca cotação atual do ativo na brapi.dev.

    Retorna dict com keys: ticker, price, change_percent, volume.
    Lança httpx.HTTPError em caso de falha de rede ou resposta inválida.
    """
    url = f"{_BRAPI_BASE}/quote/{ticker.upper()}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_brapi_headers())
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        raise ValueError(f"Ticker '{ticker}' não encontrado na brapi.dev.")

    r = results[0]
    return {
        "ticker": r.get("symbol", ticker).upper(),
        "price": Decimal(str(r.get("regularMarketPrice", 0))),
        "change_percent": r.get("regularMarketChangePercent"),
        "volume": r.get("regularMarketVolume"),
    }


async def get_quote(db: AsyncSession, ticker: str) -> MarketQuote:
    """Retorna cotação do cache ou busca na API se expirada (NFR7).

    A janela de cache é controlada por settings.market_data_cache_minutes.
    """
    ticker = ticker.upper()
    cache_limit = datetime.now(timezone.utc) - timedelta(minutes=settings.market_data_cache_minutes)

    result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == ticker))
    cached = result.scalar_one_or_none()

    if cached is not None:
        # Normaliza updated_at para comparação com timezone-aware datetime
        updated = cached.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated >= cache_limit:
            return cached

    # Cache ausente ou expirado — busca na API
    quote_data = await fetch_quote_from_api(ticker)

    if cached is None:
        cached = MarketQuote(ticker=ticker)
        db.add(cached)

    cached.price = quote_data["price"]
    cached.change_percent = quote_data["change_percent"]
    cached.volume = quote_data["volume"]
    cached.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(cached)
    return cached


# ──────────────────────────────────────────────────────────────────────────────
# Dividendos
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_dividends_from_api(ticker: str) -> list[dict]:
    """Busca histórico de proventos na brapi.dev.

    Retorna lista de dicts com keys: value, ex_date, payment_date, dividend_type.
    """
    url = f"{_BRAPI_BASE}/quote/{ticker.upper()}"
    params = {"fundamental": "false", "dividends": "true"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_brapi_headers())
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return []

    dividends_raw = results[0].get("dividendsData", {}).get("cashDividends", [])
    dividends: list[dict] = []

    for d in dividends_raw:
        try:
            from datetime import date as date_type

            ex_date_str = d.get("lastDatePrior") or d.get("ex_date")
            pay_date_str = d.get("paymentDate") or d.get("payment_date")

            ex_date = date_type.fromisoformat(ex_date_str[:10]) if ex_date_str else None
            pay_date = date_type.fromisoformat(pay_date_str[:10]) if pay_date_str else None

            if ex_date is None:
                continue

            dividends.append(
                {
                    "value": Decimal(str(d.get("rate", 0))),
                    "ex_date": ex_date,
                    "payment_date": pay_date,
                    "dividend_type": _normalize_dividend_type(d.get("label", "DIVIDENDO")),
                }
            )
        except (ValueError, KeyError):
            continue

    return dividends


def _normalize_dividend_type(label: str) -> str:
    label = label.upper()
    if "JCP" in label or "JUROS" in label:
        return "JCP"
    if "AMORT" in label:
        return "AMORTIZACAO"
    if "REND" in label:
        return "RENDIMENTO"
    return "DIVIDENDO"


async def sync_dividends(db: AsyncSession, ticker: str) -> list[Dividend]:
    """Sincroniza proventos do ticker com o banco de dados.

    Registros com a mesma (ticker, ex_date) não são duplicados.
    Retorna lista de Dividend persistidos.
    """
    ticker = ticker.upper()
    dividends_data = await fetch_dividends_from_api(ticker)

    # Busca ex_dates já existentes para evitar duplicatas
    existing_result = await db.execute(
        select(Dividend.ex_date).where(Dividend.ticker == ticker)
    )
    existing_dates = {row[0] for row in existing_result.all()}

    new_dividends: list[Dividend] = []
    for d in dividends_data:
        if d["ex_date"] in existing_dates:
            continue
        div = Dividend(
            ticker=ticker,
            value=d["value"],
            ex_date=d["ex_date"],
            payment_date=d["payment_date"],
            dividend_type=d["dividend_type"],
        )
        db.add(div)
        new_dividends.append(div)

    if new_dividends:
        await db.commit()

    return new_dividends


async def get_dividends(db: AsyncSession, ticker: str) -> list[Dividend]:
    """Retorna proventos do banco (sincronizando se necessário)."""
    ticker = ticker.upper()
    result = await db.execute(
        select(Dividend)
        .where(Dividend.ticker == ticker)
        .order_by(Dividend.ex_date.desc())
    )
    dividends = list(result.scalars().all())

    # Se não há dados, tenta sincronizar
    if not dividends:
        await sync_dividends(db, ticker)
        result = await db.execute(
            select(Dividend)
            .where(Dividend.ticker == ticker)
            .order_by(Dividend.ex_date.desc())
        )
        dividends = list(result.scalars().all())

    return dividends
