"""Testes de integração para os endpoints /api/market/.

Usa mock do httpx para evitar chamadas reais à brapi.dev,
garantindo testes determinísticos e sem dependência de rede.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote


async def _register_and_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Trader", "email": "trader@test.com", "password": "senha123"},
    )
    return resp.json()["token"]["access_token"]


def _mock_brapi_quote(ticker: str, price: float = 10.50):
    """Cria um mock de resposta da brapi.dev para cotação."""
    return {
        "results": [
            {
                "symbol": ticker,
                "regularMarketPrice": price,
                "regularMarketChangePercent": -0.5,
                "regularMarketVolume": 1500000,
            }
        ]
    }


# ── Cotações ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quote_from_api(client: AsyncClient):
    """Busca cotação na API quando cache está vazio."""
    token = await _register_and_token(client)

    mock_resp = AsyncMock()
    mock_resp.json.return_value = _mock_brapi_quote("MXRF11", 10.50)
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        resp = await client.get(
            "/api/market/quote/MXRF11",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MXRF11"
    assert float(data["price"]) == pytest.approx(10.50)


@pytest.mark.asyncio
async def test_get_quote_from_cache(client: AsyncClient, db_session: AsyncSession):
    """Deve usar cache se updated_at for recente."""
    token = await _register_and_token(client)

    # Insere cotação no cache manualmente
    quote = MarketQuote(
        ticker="HGLG11",
        price=Decimal("120.00"),
        change_percent=Decimal("0.5"),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(quote)
    await db_session.commit()

    # Não deve chamar a API externa
    with patch("httpx.AsyncClient.get") as mock_get:
        resp = await client.get(
            "/api/market/quote/HGLG11",
            headers={"Authorization": f"Bearer {token}"},
        )
        mock_get.assert_not_called()

    assert resp.status_code == 200
    assert float(resp.json()["price"]) == pytest.approx(120.00)


@pytest.mark.asyncio
async def test_get_quote_requires_auth(client: AsyncClient):
    resp = await client.get("/api/market/quote/MXRF11")
    assert resp.status_code == 401


# ── DY ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dy_with_data(client: AsyncClient, db_session: AsyncSession):
    """DY deve ser calculado corretamente com cotação e dividendos no banco."""
    token = await _register_and_token(client)

    # Seed: cotação + 12 dividendos mensais
    from datetime import timedelta

    quote = MarketQuote(
        ticker="XPML11",
        price=Decimal("100.00"),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(quote)

    for i in range(12):
        db_session.add(
            Dividend(
                ticker="XPML11",
                value=Decimal("0.80"),
                ex_date=date.today() - timedelta(days=i * 28),
                dividend_type="RENDIMENTO",
            )
        )
    await db_session.commit()

    resp = await client.get(
        "/api/market/dy/XPML11",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "XPML11"
    # DY esperado ≈ (12 * 0.80) / 100 * 100 = 9.6%
    assert data["current_dy"] is not None
    assert float(data["current_dy"]) == pytest.approx(9.6, abs=0.2)


@pytest.mark.asyncio
async def test_get_dy_no_data(client: AsyncClient):
    """DY deve retornar current_dy=None quando não há dados."""
    token = await _register_and_token(client)
    resp = await client.get(
        "/api/market/dy/SEMDATA11",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["current_dy"] is None


# ── Preço-teto ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ceiling(client: AsyncClient, db_session: AsyncSession):
    """Preço-teto deve ser calculado para DY desejado de 6%."""
    token = await _register_and_token(client)

    from datetime import timedelta

    quote = MarketQuote(
        ticker="TETO11",
        price=Decimal("15.00"),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(quote)

    # 12 dividendos de R$0,10 = R$1,20/ano → teto = 1,20/0,06 = R$20,00
    for i in range(12):
        db_session.add(
            Dividend(
                ticker="TETO11",
                value=Decimal("0.10"),
                ex_date=date.today() - timedelta(days=i * 30),
                dividend_type="DIVIDENDO",
            )
        )
    await db_session.commit()

    resp = await client.get(
        "/api/market/ceiling/TETO11?desired_dy=6.0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["barsi_ceiling"]) == pytest.approx(20.00, abs=0.05)
    # R$15 < R$20 → oportunidade
    assert data["is_below_ceiling"] is True
    assert float(data["ceiling_distance_pct"]) > 0
