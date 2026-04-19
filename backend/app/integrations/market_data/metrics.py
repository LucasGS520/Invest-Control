"""Coleta de metricas operacionais do fluxo de dados de mercado.

Metricas em memoria — reiniciadas a cada restart da aplicacao. Expostas via
GET /health/market e revisadas periodicamente pelo scheduler. Para alerting
externo (Slack, PagerDuty) ou persistencia, integrar Prometheus/push neste modulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketMetrics:
    """Acumula contadores do fluxo de mercado desde o ultimo restart."""

    cache_hits: int = 0
    cache_misses: int = 0
    fallback_activations: int = 0
    quote_errors: dict[str, int] = field(default_factory=dict)
    circuit_breaker_opens: dict[str, int] = field(default_factory=dict)

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def record_fallback(self) -> None:
        self.fallback_activations += 1

    def record_quote_error(self, provider: str) -> None:
        self.quote_errors[provider] = self.quote_errors.get(provider, 0) + 1

    def record_circuit_breaker_open(self, provider: str) -> None:
        self.circuit_breaker_opens[provider] = self.circuit_breaker_opens.get(provider, 0) + 1

    def cache_hit_rate(self) -> float | None:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else None

    def total_errors(self) -> int:
        return sum(self.quote_errors.values())

    def error_rate(self) -> float | None:
        """Taxa de erro sobre o total de requisicoes que chegaram aos providers."""
        if self.cache_misses == 0:
            return None
        return self.total_errors() / self.cache_misses

    def summary(self) -> dict:
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate(), 4) if self.cache_hit_rate() is not None else None,
            "fallback_activations": self.fallback_activations,
            "quote_errors_by_provider": dict(self.quote_errors),
            "circuit_breaker_opens_by_provider": dict(self.circuit_breaker_opens),
        }

    def reset(self) -> None:
        """Reinicia todos os contadores (util para janelas de medicao periodica)."""
        self.cache_hits = 0
        self.cache_misses = 0
        self.fallback_activations = 0
        self.quote_errors.clear()
        self.circuit_breaker_opens.clear()


# Singleton compartilhado por aggregator, health endpoint e scheduler
market_metrics = MarketMetrics()
