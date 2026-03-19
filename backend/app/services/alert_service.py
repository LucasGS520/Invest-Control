"""Serviço de Alertas Inteligentes (FR8).

Avalia condições de mercado e marca alertas como disparados.
O verificador é chamado pelo scheduler periodicamente.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.alert import Alert
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.services.rules_engine import calculate_barsi_ceiling

logger = logging.getLogger(__name__)

# Intervalo mínimo entre disparos do mesmo alerta (evita spam)
_RETRIGGER_HOURS = 24


async def check_alert(db: AsyncSession, alert: Alert) -> bool:
    """Avalia se a condição de um alerta foi atingida.

    Retorna True se o alerta deve disparar, False caso contrário.
    """
    # Evita re-disparar dentro da janela de supressão
    if alert.triggered_at:
        since = datetime.now(UTC) - alert.triggered_at.replace(tzinfo=UTC)
        if since < timedelta(hours=_RETRIGGER_HOURS):
            return False

    ticker = alert.ticker.upper()

    if alert.alert_type in ("PRICE_BELOW", "PRICE_ABOVE"):
        price_row = await db.execute(
            select(MarketQuote.price).where(MarketQuote.ticker == ticker)
        )
        price = price_row.scalar_one_or_none()
        if price is None or alert.threshold is None:
            return False
        current = Decimal(str(price))
        threshold = Decimal(str(alert.threshold))
        if alert.alert_type == "PRICE_BELOW":
            return current <= threshold
        return current >= threshold

    if alert.alert_type == "BELOW_CEILING":
        price_row = await db.execute(
            select(MarketQuote.price).where(MarketQuote.ticker == ticker)
        )
        price = price_row.scalar_one_or_none()
        if price is None:
            return False
        ceiling = await calculate_barsi_ceiling(db, ticker, Decimal("6.0"))
        if ceiling is None:
            return False
        return Decimal(str(price)) < ceiling

    if alert.alert_type == "EX_DATE":
        days = alert.days_before_ex or 7
        cutoff = date.today() + timedelta(days=days)
        result = await db.execute(
            select(Dividend).where(
                Dividend.ticker == ticker,
                Dividend.ex_date >= date.today(),
                Dividend.ex_date <= cutoff,
            )
        )
        return result.scalar_one_or_none() is not None

    return False


async def evaluate_all_alerts(db: AsyncSession) -> int:
    """Avalia todos os alertas ativos e marca os disparados.

    Retorna o número de alertas disparados nesta execução.
    """
    result = await db.execute(select(Alert).where(Alert.is_active == True))  # noqa: E712
    alerts = result.scalars().all()

    triggered_count = 0
    for alert in alerts:
        try:
            should_fire = await check_alert(db, alert)
            if should_fire:
                alert.triggered_at = datetime.now(UTC)
                triggered_count += 1
                logger.info(
                    "[alert] Disparado — user_id=%d ticker=%s tipo=%s",
                    alert.user_id,
                    alert.ticker,
                    alert.alert_type,
                )
        except Exception as exc:
            logger.warning("[alert] Erro ao avaliar alerta id=%d: %s", alert.id, exc)

    await db.commit()
    return triggered_count
