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


def start_scheduler() -> None:
    """Registra jobs e inicia o scheduler.

    Chamado no evento de startup da aplicação FastAPI.
    """
    from app.core.config import settings

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

    scheduler.start()
    logger.info("[scheduler] Iniciado — cotações a cada %d min, dividendos diariamente às 7h")


def stop_scheduler() -> None:
    """Para o scheduler graciosamente no shutdown da aplicação."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] Encerrado.")
