"""Contratos base para integracoes de dados de mercado."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Quote(BaseModel):
    """Representa uma cotacao unificada vinda de um provider externo."""

    ticker: str
    price: Decimal
    change_percent: Decimal | None = None
    volume: Decimal | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class DividendItem(BaseModel):
    """Representa um evento de provento normalizado entre providers."""

    ticker: str
    value: Decimal
    ex_date: date
    payment_date: date | None = None
    dividend_type: str = "DIVIDENDO"
    source: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("dividend_type")
    @classmethod
    def normalize_dividend_type(cls, value: str) -> str:
        return value.strip().upper()


class BaseProvider(ABC):
    """Base comum para providers com metadados compartilhados."""

    provider_name: str = "unknown"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds


class BasePriceProvider(BaseProvider):
    """Contrato para providers de preco/cotacao."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> Quote:
        """Retorna a cotacao atual de um ticker."""

    async def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        """Fallback padrao para providers sem endpoint batch nativo."""

        quotes: dict[str, Quote] = {}
        for ticker in tickers:
            quote = await self.get_quote(ticker)
            quotes[quote.ticker] = quote
        return quotes


class BaseDividendProvider(BaseProvider):
    """Contrato para providers que entregam historico de proventos."""

    @abstractmethod
    async def get_dividends(self, ticker: str) -> list[DividendItem]:
        """Retorna os proventos conhecidos para um ticker."""


class AssetInfo(BaseModel):
    """Metadados de um ativo retornados por um provider externo."""

    ticker: str
    name: str
    sector: str | None = None
    subsector: str | None = None
    asset_type: str = "ACAO"
    logo_url: str | None = None
    source: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class BaseAssetInfoProvider(BaseProvider):
    """Contrato para providers que retornam metadados de ativos."""

    @abstractmethod
    async def get_asset_info(self, ticker: str) -> AssetInfo:
        """Retorna nome, setor e tipo de um ativo pelo ticker."""
