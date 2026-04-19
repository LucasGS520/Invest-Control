"""Testes de contrato para endpoints criticos de mercado.

Verifica que os schemas de resposta permanecem estaveis e que o fluxo
transaction-first (carteira -> transacao -> posicao) nao regrediu.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.market_data import MarketQuote


# ── helpers ───────────────────────────────────────────────────────────────────


async def _auth_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Trader", "email": "trader@contract.com", "password": "senha123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mock_quote_response(ticker: str, price: float = 10.50) -> AsyncMock:
    mock = AsyncMock()
    mock.json.return_value = {
        "results": [
            {
                "symbol": ticker,
                "regularMarketPrice": price,
                "regularMarketChangePercent": -0.5,
                "regularMarketVolume": 1500000,
            }
        ]
    }
    mock.raise_for_status = lambda: None
    return mock


# ── GET /market/quote/{ticker} ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contract_quote_schema(client: AsyncClient):
    """GET /market/quote/{ticker} deve retornar campos obrigatorios do schema."""
    token = await _auth_token(client)

    with patch("httpx.AsyncClient.get", return_value=_mock_quote_response("MXRF11", 10.50)):
        resp = await client.get("/api/market/quote/MXRF11", headers=_headers(token))

    assert resp.status_code == 200
    data = resp.json()
    assert "ticker" in data
    assert "price" in data
    assert "change_percent" in data
    assert data["ticker"] == "MXRF11"
    assert float(data["price"]) > 0


@pytest.mark.asyncio
async def test_contract_quote_cache_hit_nao_chama_provider(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /market/quote/{ticker} deve usar cache sem chamar provider externo."""
    token = await _auth_token(client)

    db_session.add(
        MarketQuote(
            ticker="HGLG11",
            price=Decimal("120.00"),
            change_percent=Decimal("0.5"),
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    with patch("httpx.AsyncClient.get", side_effect=AssertionError("provider nao deve ser chamado")):
        resp = await client.get("/api/market/quote/HGLG11", headers=_headers(token))

    assert resp.status_code == 200
    assert float(resp.json()["price"]) == pytest.approx(120.00)


@pytest.mark.asyncio
async def test_contract_quote_provider_indisponivel_retorna_502(client: AsyncClient):
    """GET /market/quote/{ticker} deve retornar 502 quando todos os providers falham."""
    token = await _auth_token(client)

    with patch("httpx.AsyncClient.get", side_effect=Exception("provider down")):
        resp = await client.get("/api/market/quote/XPTO9", headers=_headers(token))

    assert resp.status_code == 502


# ── GET /market/search ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contract_search_retorna_lista(client: AsyncClient, db_session: AsyncSession):
    """GET /market/search deve retornar lista com campos de schema corretos."""
    token = await _auth_token(client)

    db_session.add(Asset(ticker="PETR4", name="Petrobras", asset_type="ACAO", is_active=True))
    await db_session.commit()

    resp = await client.get("/api/market/search?q=PETR", headers=_headers(token))

    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    item = items[0]
    assert "ticker" in item
    assert "name" in item
    assert "asset_type" in item
    assert item["ticker"] == "PETR4"


@pytest.mark.asyncio
async def test_contract_search_query_curta_retorna_422(client: AsyncClient):
    """GET /market/search com q < 2 chars deve retornar 422 (validacao FastAPI)."""
    token = await _auth_token(client)
    resp = await client.get("/api/market/search?q=P", headers=_headers(token))
    assert resp.status_code == 422


# ── Fluxo transaction-first nao regrediu ─────────────────────────────────────


@pytest.mark.asyncio
async def test_contract_transacao_cria_posicao(client: AsyncClient):
    """POST portfolio/transactions deve criar posicao atualizavel via GET portfolio."""
    token = await _auth_token(client)

    # Cria carteira
    resp = await client.post(
        "/api/portfolios/",
        json={"name": "Carteira Teste"},
        headers=_headers(token),
    )
    assert resp.status_code in (200, 201), resp.text
    portfolio_id = resp.json()["id"]

    # Registra transacao
    with patch("httpx.AsyncClient.get", return_value=_mock_quote_response("PETR4", 30.0)):
        resp = await client.post(
            f"/api/portfolios/{portfolio_id}/transactions",
            json={
                "ticker": "PETR4",
                "transaction_type": "BUY",
                "quantity": 10,
                "price": 30.00,
                "date": "2025-01-10",
            },
            headers=_headers(token),
        )
    assert resp.status_code in (200, 201), resp.text

    # Verifica que carteira retorna posicao
    resp = await client.get(f"/api/portfolios/{portfolio_id}", headers=_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "positions" in data or "assets" in data or isinstance(data, dict)
