"""Testes unitários para o motor de regras (DY e preço-teto Barsi).

Usa o banco SQLite em memória via conftest.py, sem chamadas externas.
Todos os dados são inseridos diretamente no banco antes de cada teste.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.services.rules_engine import (
    calculate_barsi_ceiling,
    calculate_dy,
    calculate_dy_history,
    identify_opportunity,
)


async def _seed_quote(db: AsyncSession, ticker: str, price: float) -> None:
    from datetime import datetime, timezone

    quote = MarketQuote(
        ticker=ticker,
        price=Decimal(str(price)),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(quote)
    await db.commit()


async def _seed_dividend(
    db: AsyncSession,
    ticker: str,
    value: float,
    days_ago: int,
    div_type: str = "DIVIDENDO",
) -> None:
    div = Dividend(
        ticker=ticker,
        value=Decimal(str(value)),
        ex_date=date.today() - timedelta(days=days_ago),
        dividend_type=div_type,
    )
    db.add(div)
    await db.commit()


# ── DY ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dy_basic(db_session: AsyncSession):
    """DY = soma_dividendos_12m / preco * 100"""
    await _seed_quote(db_session, "MXRF11", 10.00)
    # 12 dividendos mensais de R$ 0,10 = R$ 1,20/ano → DY = 12%
    for i in range(12):
        await _seed_dividend(db_session, "MXRF11", 0.10, days_ago=i * 30)

    dy = await calculate_dy(db_session, "MXRF11")
    assert dy is not None
    assert dy == pytest.approx(Decimal("12.00"), abs=Decimal("0.10"))


@pytest.mark.asyncio
async def test_dy_no_price_returns_none(db_session: AsyncSession):
    """Sem cotação cadastrada deve retornar None."""
    await _seed_dividend(db_session, "NOVT3", 0.50, days_ago=10)
    dy = await calculate_dy(db_session, "NOVT3")
    assert dy is None


@pytest.mark.asyncio
async def test_dy_no_dividends_returns_none(db_session: AsyncSession):
    """Sem histórico de dividendos deve retornar None."""
    await _seed_quote(db_session, "ISEM3", 20.00)
    dy = await calculate_dy(db_session, "ISEM3")
    assert dy is None


@pytest.mark.asyncio
async def test_dy_excludes_old_dividends(db_session: AsyncSession):
    """Dividendos há mais de 12 meses não devem entrar no cálculo padrão."""
    await _seed_quote(db_session, "HGLG11", 100.00)
    # Antigo (fora da janela)
    await _seed_dividend(db_session, "HGLG11", 5.00, days_ago=400)
    # Recente (dentro da janela)
    await _seed_dividend(db_session, "HGLG11", 1.00, days_ago=10)

    dy = await calculate_dy(db_session, "HGLG11")
    assert dy is not None
    # Apenas R$1,00 → DY = 12% (anualizado para 12 meses), não 72%
    assert dy < Decimal("20")


# ── Preço-teto Barsi ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_barsi_ceiling_basic(db_session: AsyncSession):
    """Teto = dividendo_anual / (DY_desejado / 100)."""
    # 12 dividendos de R$0,10 = R$1,20/ano
    # Teto para DY desejado 6% = 1,20 / 0,06 = R$20,00
    for i in range(12):
        await _seed_dividend(db_session, "CALC11", 0.10, days_ago=i * 30)

    ceiling = await calculate_barsi_ceiling(db_session, "CALC11", desired_dy=Decimal("6.0"))
    assert ceiling is not None
    assert ceiling == pytest.approx(Decimal("20.00"), abs=Decimal("0.05"))


@pytest.mark.asyncio
async def test_barsi_ceiling_no_dividends(db_session: AsyncSession):
    """Sem dividendos, o preço-teto deve ser None."""
    ceiling = await calculate_barsi_ceiling(db_session, "NDIV3", desired_dy=Decimal("6.0"))
    assert ceiling is None


@pytest.mark.asyncio
async def test_barsi_ceiling_desired_dy_zero_returns_none(db_session: AsyncSession):
    """DY desejado = 0 não deve ser calculado."""
    ceiling = await calculate_barsi_ceiling(db_session, "ANY11", desired_dy=Decimal("0"))
    assert ceiling is None


# ── DY Histórico ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dy_history_returns_years(db_session: AsyncSession):
    await _seed_quote(db_session, "HIST11", 10.00)
    # Dividendo no ano atual
    await _seed_dividend(db_session, "HIST11", 0.10, days_ago=10)

    history = await calculate_dy_history(db_session, "HIST11", years=3)
    assert len(history) == 3
    # Ano atual deve ter DY calculado
    assert history[0]["year"] == date.today().year
    assert history[0]["dy_percent"] is not None


# ── Identificação de oportunidade ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_opportunity_below_ceiling(db_session: AsyncSession):
    """Preço abaixo do teto → is_below_ceiling = True."""
    # Teto calculado = R$20,00 | Preço atual = R$15,00 → oportunidade
    await _seed_quote(db_session, "OPRT11", 15.00)
    for i in range(12):
        await _seed_dividend(db_session, "OPRT11", 0.10, days_ago=i * 30)

    result = await identify_opportunity(db_session, "OPRT11", desired_dy=Decimal("6.0"))
    assert result["is_below_ceiling"] is True
    assert result["ceiling_distance_pct"] > 0


@pytest.mark.asyncio
async def test_opportunity_above_ceiling(db_session: AsyncSession):
    """Preço acima do teto → is_below_ceiling = False."""
    # Teto calculado = R$20,00 | Preço atual = R$25,00 → fora da zona
    await _seed_quote(db_session, "CARA11", 25.00)
    for i in range(12):
        await _seed_dividend(db_session, "CARA11", 0.10, days_ago=i * 30)

    result = await identify_opportunity(db_session, "CARA11", desired_dy=Decimal("6.0"))
    assert result["is_below_ceiling"] is False
    assert result["ceiling_distance_pct"] < 0
