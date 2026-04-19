"""Implementa endpoints simples para verificar a saúde da aplicação."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse, MarketHealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Verifica o estado da API")
def read_health() -> HealthResponse:
    """Retorna um resumo mínimo para monitoramento local e integração futura."""
    return HealthResponse(
        status="ok",
        application=settings.app_name,
        environment=settings.app_env,
        version="0.1.0",
    )


@router.get(
    "/health/market",
    response_model=MarketHealthResponse,
    summary="Saúde operacional do fluxo de dados de mercado",
)
def read_market_health() -> MarketHealthResponse:
    """Expõe métricas de cache, fallback, circuit breaker e status de SLO.

    Retorna status 'degraded' quando qualquer SLO está em violação.
    Use para monitoramento, alertas e revisão periódica de saúde.
    """
    from app.integrations.market_data.aggregator import market_data_aggregator
    from app.integrations.market_data.metrics import market_metrics

    hit_rate = market_metrics.cache_hit_rate()
    error_rate = market_metrics.error_rate()

    slo_issues: list[str] = []

    if hit_rate is not None and hit_rate < settings.market_slo_min_cache_hit_rate:
        slo_issues.append(
            f"cache_hit_rate={hit_rate:.2%} abaixo do SLO={settings.market_slo_min_cache_hit_rate:.0%}"
        )
    if error_rate is not None and error_rate > settings.market_slo_max_error_rate:
        slo_issues.append(
            f"error_rate={error_rate:.2%} acima do SLO={settings.market_slo_max_error_rate:.0%}"
        )

    open_circuits = [
        name
        for name in market_data_aggregator._price_providers
        if market_data_aggregator._circuit_breaker.is_open(name)
    ]
    if open_circuits:
        slo_issues.append(f"circuit_breakers_abertos={open_circuits}")

    slo_ok = len(slo_issues) == 0
    summary = market_metrics.summary()

    return MarketHealthResponse(
        status="ok" if slo_ok else "degraded",
        slo_ok=slo_ok,
        slo_issues=slo_issues,
        open_circuits=open_circuits,
        **summary,
    )
