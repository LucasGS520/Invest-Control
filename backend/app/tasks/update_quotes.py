"""Tarefas periódicas: atualização automática de cotações e dividendos.

Usa APScheduler para agendar atualizações em background (NFR1, NFR2).
As tarefas rodam em janelas configuráveis, evitando sobrecarga na API externa.

Agenda padrão:
- Cotações: a cada 15 minutos (configurável via MARKET_DATA_CACHE_MINUTES)
- Dividendos: diariamente às 7h (mercado ainda fechado)
"""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.models.asset import Asset
from app.db.session import AsyncSessionLocal
from app.services import market_data_service as mds
from app.services.alert_service import evaluate_all_alerts

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")


async def _update_all_quotes() -> None:
    """Atualiza cotações de todos os ativos ativos cadastrados."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Asset.ticker).where(Asset.is_active == True))  # noqa: E712
        tickers = [row[0] for row in result.all()]

    if not tickers:
        return

    logger.info("[scheduler] Atualizando cotações de %d ativos — %s", len(tickers), datetime.now(UTC))

    async with AsyncSessionLocal() as db:
        try:
            await mds.get_quotes(db, tickers)
            return
        except Exception as exc:
            logger.warning("[scheduler] Falha no batch de cotações, usando fallback unitário: %s", exc)

        for ticker in tickers:
            try:
                await mds.get_quote(db, ticker)
            except Exception as exc:
                logger.warning("[scheduler] Falha ao atualizar %s: %s", ticker, exc)


async def _sync_all_dividends() -> None:
    """Sincroniza dividendos de todos os ativos ativos."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Asset.ticker).where(Asset.is_active == True))  # noqa: E712
        tickers = [row[0] for row in result.all()]

    if not tickers:
        return

    logger.info("[scheduler] Sincronizando dividendos de %d ativos", len(tickers))

    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            try:
                await mds.sync_dividends(db, ticker)
            except Exception as exc:
                logger.warning("[scheduler] Falha ao sincronizar dividendos de %s: %s", ticker, exc)


async def _review_market_health() -> None:
    """Revisao periodica de saude dos providers e SLOs de mercado.

    Loga um resumo das metricas acumuladas e emite WARNING se algum SLO
    estiver em violacao. Para alerting externo (Slack, PagerDuty), adicionar
    integracao aqui.
    """
    from app.core.config import settings
    from app.integrations.market_data.aggregator import market_data_aggregator
    from app.integrations.market_data.metrics import market_metrics

    summary = market_metrics.summary()
    hit_rate = market_metrics.cache_hit_rate()
    error_rate = market_metrics.error_rate()
    open_circuits = [
        name
        for name in market_data_aggregator._price_providers
        if market_data_aggregator._circuit_breaker.is_open(name)
    ]

    logger.info("[health-review] metricas_mercado %s", summary)

    issues: list[str] = []
    if hit_rate is not None and hit_rate < settings.market_slo_min_cache_hit_rate:
        issues.append(f"cache_hit_rate={hit_rate:.2%} < slo={settings.market_slo_min_cache_hit_rate:.0%}")
    if error_rate is not None and error_rate > settings.market_slo_max_error_rate:
        issues.append(f"error_rate={error_rate:.2%} > slo={settings.market_slo_max_error_rate:.0%}")
    if open_circuits:
        issues.append(f"circuit_breakers_abertos={open_circuits}")

    if issues:
        logger.warning("[health-review] SLO_VIOLADO issues=%s", issues)
    else:
        logger.info("[health-review] SLO_OK todos os indicadores dentro do limite")


async def _check_all_alerts() -> None:
    """Avalia todos os alertas ativos e registra os disparados."""
    async with AsyncSessionLocal() as db:
        try:
            fired = await evaluate_all_alerts(db)
            if fired:
                logger.info("[scheduler] Alertas disparados: %d", fired)
        except Exception as exc:
            logger.warning("[scheduler] Erro ao avaliar alertas: %s", exc)


def start_scheduler() -> None:
    """Registra jobs e inicia o scheduler.

    Chamado no evento de startup da aplicação FastAPI.
    """
    from app.core.config import settings

    if not settings.market_sync_enabled:
        logger.warning("[scheduler] market_sync_enabled=false — jobs de mercado desabilitados")
        return

    # Cotações: intervalo baseado na configuração de cache
    scheduler.add_job(
        _update_all_quotes,
        trigger="interval",
        minutes=settings.market_data_cache_minutes,
        id="update_quotes",
        replace_existing=True,
    )

    # Dividendos: uma vez por dia às 7h (horário de Brasília)
    scheduler.add_job(
        _sync_all_dividends,
        trigger="cron",
        hour=7,
        minute=0,
        id="sync_dividends",
        replace_existing=True,
    )

    # Alertas: a cada 30 minutos
    scheduler.add_job(
        _check_all_alerts,
        trigger="interval",
        minutes=30,
        id="check_alerts",
        replace_existing=True,
    )

    # Revisão de saúde dos providers: toda segunda-feira às 9h
    scheduler.add_job(
        _review_market_health,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="review_market_health",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[scheduler] Iniciado — cotações a cada %d min, dividendos às 7h, alertas a cada 30min")


def stop_scheduler() -> None:
    """Para o scheduler graciosamente no shutdown da aplicação."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] Encerrado.")
