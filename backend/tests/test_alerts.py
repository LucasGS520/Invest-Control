"""Testes para o sistema de Alertas Inteligentes (FR8)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.alert import Alert
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.user import User
from app.services.alert_service import check_alert


# ── Helpers ────────────────────────────────────────────────────────────────


async def _register_and_token(client: AsyncClient, email: str = "alert@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Alert User", "email": email, "password": "senha123"},
    )
    assert resp.status_code == 201
    return resp.json()["token"]["access_token"]


# ── Testes unitários do serviço ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_alert_price_below_triggered(db_session: AsyncSession):
    """PRICE_BELOW dispara quando preço ≤ threshold."""
    db_session.add(MarketQuote(ticker="MXRF11", price=Decimal("9.50")))
    user = User(name="U", email="u@u.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    alert = Alert(user_id=user.id, ticker="MXRF11", alert_type="PRICE_BELOW", threshold=10.0)
    db_session.add(alert)
    await db_session.commit()

    assert await check_alert(db_session, alert) is True


@pytest.mark.asyncio
async def test_check_alert_price_below_not_triggered(db_session: AsyncSession):
    """PRICE_BELOW não dispara quando preço > threshold."""
    db_session.add(MarketQuote(ticker="MXRF11", price=Decimal("10.50")))
    user = User(name="U2", email="u2@u.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    alert = Alert(user_id=user.id, ticker="MXRF11", alert_type="PRICE_BELOW", threshold=10.0)
    db_session.add(alert)
    await db_session.commit()

    assert await check_alert(db_session, alert) is False


@pytest.mark.asyncio
async def test_check_alert_price_above_triggered(db_session: AsyncSession):
    """PRICE_ABOVE dispara quando preço ≥ threshold."""
    db_session.add(MarketQuote(ticker="ITUB4", price=Decimal("32.00")))
    user = User(name="U3", email="u3@u.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    alert = Alert(user_id=user.id, ticker="ITUB4", alert_type="PRICE_ABOVE", threshold=30.0)
    db_session.add(alert)
    await db_session.commit()

    assert await check_alert(db_session, alert) is True


@pytest.mark.asyncio
async def test_check_alert_ex_date_triggered(db_session: AsyncSession):
    """EX_DATE dispara quando há ex-date dentro dos dias configurados."""
    user = User(name="U4", email="u4@u.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    near_ex = date.today() + timedelta(days=5)
    db_session.add(
        Dividend(ticker="MXRF11", value=Decimal("0.10"), ex_date=near_ex, dividend_type="RENDIMENTO")
    )

    alert = Alert(user_id=user.id, ticker="MXRF11", alert_type="EX_DATE", days_before_ex=7)
    db_session.add(alert)
    await db_session.commit()

    assert await check_alert(db_session, alert) is True


@pytest.mark.asyncio
async def test_check_alert_ex_date_not_triggered(db_session: AsyncSession):
    """EX_DATE não dispara quando ex-date está além do prazo configurado."""
    user = User(name="U5", email="u5@u.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    far_ex = date.today() + timedelta(days=60)
    db_session.add(
        Dividend(ticker="MXRF11", value=Decimal("0.10"), ex_date=far_ex, dividend_type="RENDIMENTO")
    )

    alert = Alert(user_id=user.id, ticker="MXRF11", alert_type="EX_DATE", days_before_ex=7)
    db_session.add(alert)
    await db_session.commit()

    assert await check_alert(db_session, alert) is False


# ── Testes de integração HTTP ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_alert_price_below(client: AsyncClient):
    """Cria alerta PRICE_BELOW com sucesso."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "PRICE_BELOW", "threshold": 9.50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "MXRF11"
    assert data["alert_type"] == "PRICE_BELOW"
    assert float(data["threshold"]) == pytest.approx(9.50)
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_alert_ex_date(client: AsyncClient):
    """Cria alerta EX_DATE com days_before_ex."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "HGLG11", "alert_type": "EX_DATE", "days_before_ex": 14},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["days_before_ex"] == 14


@pytest.mark.asyncio
async def test_create_alert_price_below_missing_threshold(client: AsyncClient):
    """PRICE_BELOW sem threshold retorna 422."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "PRICE_BELOW"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient):
    """Lista retorna apenas alertas do usuário autenticado."""
    token = await _register_and_token(client)
    await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/alerts/",
        json={"ticker": "HGLG11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/api/alerts/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_alerts_isolation(client: AsyncClient):
    """Usuário B não vê alertas de A."""
    token_a = await _register_and_token(client, email="a_alert@test.com")
    await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    token_b = await _register_and_token(client, email="b_alert@test.com")
    resp = await client.get("/api/alerts/", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_toggle_alert(client: AsyncClient):
    """PATCH desativa e reativa o alerta."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token}"},
    )
    alert_id = resp.json()["id"]

    # Desativa
    patch = await client.patch(
        f"/api/alerts/{alert_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch.status_code == 200
    assert patch.json()["is_active"] is False

    # Reativa
    patch2 = await client.patch(
        f"/api/alerts/{alert_id}",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_delete_alert(client: AsyncClient):
    """DELETE remove o alerta."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token}"},
    )
    alert_id = resp.json()["id"]

    del_resp = await client.delete(
        f"/api/alerts/{alert_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert del_resp.status_code == 204

    # Confirma remoção
    get_resp = await client.get(
        f"/api/alerts/{alert_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_alert_not_accessible_by_other_user(client: AsyncClient):
    """GET/DELETE de alerta de outro usuário retorna 404."""
    token_a = await _register_and_token(client, email="own_a@test.com")
    resp = await client.post(
        "/api/alerts/",
        json={"ticker": "MXRF11", "alert_type": "BELOW_CEILING"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    alert_id = resp.json()["id"]

    token_b = await _register_and_token(client, email="own_b@test.com")
    get_resp = await client.get(
        f"/api/alerts/{alert_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert get_resp.status_code == 404
