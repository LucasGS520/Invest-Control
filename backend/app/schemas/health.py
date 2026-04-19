"""Schemas usados na resposta do endpoint de saúde da API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Representa o estado básico da aplicação durante o bootstrap do MVP."""

    status: str
    application: str
    environment: str
    version: str


class MarketHealthResponse(BaseModel):
    """Saúde operacional do fluxo de dados de mercado com status de SLO."""

    status: str
    slo_ok: bool
    slo_issues: list[str]
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float | None
    fallback_activations: int
    quote_errors_by_provider: dict[str, int]
    circuit_breaker_opens_by_provider: dict[str, int]
    open_circuits: list[str]
