"""Testes para o Calendário de Proventos (FR5)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.dividend import Dividend
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.user import User


# ── Helpers ────────────────────────────────────────────────────────────────


async def _register_and_token(client: AsyncClient, email: str = "cal@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Cal User", "email": email, "password": "senha123"},
    )
    assert resp.status_code == 201
    return resp.json()["token"]["access_token"]


async def _setup_portfolio_with_position(
    db: AsyncSession, email: str = "cal@test.com"
) -> tuple[int, int]:
    """Cria usuário, carteira e posição. Retorna (portfolio_id, asset_id)."""
    user = User(name="Cal", email=email, hashed_password="x")
    db.add(user)
    await db.flush()

    portfolio = Portfolio(user_id=user.id, name="Teste Cal")
    db.add(portfolio)
    await db.flush()

    asset = Asset(ticker="MXRF11", name="Maxi Renda", asset_type="FII")
    db.add(asset)
    await db.flush()

    pos = PortfolioAsset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=10,
        avg_price=Decimal("10.00"),
    )
    db.add(pos)
    await db.commit()

    return portfolio.id, asset.id


# ── Testes ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_unauthorized(client: AsyncClient):
    """Sem token → 401."""
    resp = await client.get("/api/calendar/dividends", params={"portfolio_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_calendar_portfolio_not_found(client: AsyncClient):
    """Carteira inexistente → 404."""
    token = await _register_and_token(client)
    resp = await client.get(
        "/api/calendar/dividends",
        params={"portfolio_id": 9999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_calendar_empty_portfolio(client: AsyncClient, db_session: AsyncSession):
    """Carteira sem posições retorna listas vazias."""
    token = await _register_and_token(client)
    portfolio_id, _ = await _setup_portfolio_with_position(db_session)

    # Remove a posição
    from sqlalchemy import delete
    from app.db.models.portfolio_asset import PortfolioAsset
    await db_session.execute(delete(PortfolioAsset))
    await db_session.commit()

    # Precisa de uma carteira sem posições — cria via API
    token2 = await _register_and_token(client, email="cal2@test.com")
    resp_p = await client.post(
        "/api/portfolios/",
        json={"name": "Vazia"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    pid = resp_p.json()["id"]

    resp = await client.get(
        "/api/calendar/dividends",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["upcoming_events"] == []
    assert data["past_events"] == []


@pytest.mark.asyncio
async def test_calendar_shows_upcoming_dividends(client: AsyncClient, db_session: AsyncSession):
    """Dividendo futuro aparece em upcoming_events."""
    token = await _register_and_token(client)

    # Cria portfolio + ativo via API para associar ao token do usuário correto
    resp_p = await client.post(
        "/api/portfolios/",
        json={"name": "FIIs"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = resp_p.json()["id"]

    resp_a = await client.post(
        "/api/assets/",
        json={"ticker": "HGLG11", "name": "CSHG Logística", "asset_type": "FII"},
        headers={"Authorization": f"Bearer {token}"},
    )
    aid = resp_a.json()["id"]

    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={
            "asset_id": aid,
            "transaction_type": "BUY",
            "quantity": 5,
            "price": 150.0,
            "date": str(date.today()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Insere dividendo futuro diretamente
    future_ex = date.today() + timedelta(days=15)
    div = Dividend(
        ticker="HGLG11",
        value=Decimal("1.50"),
        ex_date=future_ex,
        payment_date=future_ex + timedelta(days=3),
        dividend_type="RENDIMENTO",
    )
    db_session.add(div)
    await db_session.commit()

    resp = await client.get(
        "/api/calendar/dividends",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["upcoming_events"]) == 1
    ev = data["upcoming_events"][0]
    assert ev["ticker"] == "HGLG11"
    assert ev["days_until_ex"] == 15
    assert float(ev["value"]) == pytest.approx(1.50)


@pytest.mark.asyncio
async def test_calendar_ticker_endpoint(client: AsyncClient, db_session: AsyncSession):
    """GET /api/calendar/dividends/{ticker} retorna eventos do ativo."""
    token = await _register_and_token(client)

    # Insere dividendo passado e futuro
    past_ex = date.today() - timedelta(days=30)
    future_ex = date.today() + timedelta(days=20)

    db_session.add_all([
        Dividend(ticker="MXRF11", value=Decimal("0.10"), ex_date=past_ex, dividend_type="RENDIMENTO"),
        Dividend(ticker="MXRF11", value=Decimal("0.12"), ex_date=future_ex, dividend_type="RENDIMENTO"),
    ])
    await db_session.commit()

    resp = await client.get(
        "/api/calendar/dividends/MXRF11",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MXRF11"
    assert len(data["upcoming_events"]) == 1
    assert len(data["past_events"]) == 1


@pytest.mark.asyncio
async def test_calendar_portfolio_isolation(client: AsyncClient):
    """Usuário B não acessa calendário da carteira de A."""
    token_a = await _register_and_token(client, email="cala@test.com")
    resp_p = await client.post(
        "/api/portfolios/",
        json={"name": "Carteira A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    pid_a = resp_p.json()["id"]

    token_b = await _register_and_token(client, email="calb@test.com")
    resp = await client.get(
        "/api/calendar/dividends",
        params={"portfolio_id": pid_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
