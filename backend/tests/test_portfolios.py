"""Testes para CRUD de carteiras, ativos e transações."""

import pytest
from httpx import AsyncClient


async def _register_and_token(client: AsyncClient, email: str = "user@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "User", "email": email, "password": "senha123"},
    )
    return resp.json()["token"]["access_token"]


async def _create_asset(client: AsyncClient, token: str, ticker: str = "MXRF11") -> dict:
    resp = await client.post(
        "/api/assets/",
        json={"ticker": ticker, "name": "Maxi Renda FII", "asset_type": "FII"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Carteiras ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_portfolio(client: AsyncClient):
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/portfolios/",
        json={"name": "Minha Carteira"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Minha Carteira"


@pytest.mark.asyncio
async def test_list_portfolios(client: AsyncClient):
    token = await _register_and_token(client)
    for name in ["Carteira A", "Carteira B"]:
        await client.post(
            "/api/portfolios/",
            json={"name": name},
            headers={"Authorization": f"Bearer {token}"},
        )
    resp = await client.get("/api/portfolios/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_portfolio_isolation(client: AsyncClient):
    token_a = await _register_and_token(client, "a@test.com")
    token_b = await _register_and_token(client, "b@test.com")

    await client.post(
        "/api/portfolios/",
        json={"name": "Carteira de A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await client.get("/api/portfolios/", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_update_portfolio(client: AsyncClient):
    token = await _register_and_token(client)
    create_resp = await client.post(
        "/api/portfolios/",
        json={"name": "Original"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/portfolios/{pid}",
        json={"name": "Atualizada"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Atualizada"


@pytest.mark.asyncio
async def test_delete_portfolio(client: AsyncClient):
    token = await _register_and_token(client)
    create_resp = await client.post(
        "/api/portfolios/",
        json={"name": "Para Deletar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = create_resp.json()["id"]
    del_resp = await client.delete(
        f"/api/portfolios/{pid}", headers={"Authorization": f"Bearer {token}"}
    )
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/portfolios/", headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()) == 0


# ── Transações ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_buy_transaction(client: AsyncClient):
    token = await _register_and_token(client)
    portfolio = await client.post(
        "/api/portfolios/", json={"name": "FIIs"}, headers={"Authorization": f"Bearer {token}"}
    )
    pid = portfolio.json()["id"]
    asset = await _create_asset(client, token)

    resp = await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={
            "asset_id": asset["id"],
            "transaction_type": "BUY",
            "quantity": 100,
            "price": "10.25",
            "date": "2026-03-19",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["ticker"] == "MXRF11"
    assert resp.json()["quantity"] == 100


@pytest.mark.asyncio
async def test_portfolio_summary_after_buy(client: AsyncClient):
    token = await _register_and_token(client)
    portfolio = await client.post(
        "/api/portfolios/", json={"name": "FIIs"}, headers={"Authorization": f"Bearer {token}"}
    )
    pid = portfolio.json()["id"]
    asset = await _create_asset(client, token)

    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={
            "asset_id": asset["id"],
            "transaction_type": "BUY",
            "quantity": 100,
            "price": "10.25",
            "date": "2026-03-19",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    summary = await client.get(
        f"/api/portfolios/{pid}", headers={"Authorization": f"Bearer {token}"}
    )
    assert summary.status_code == 200
    data = summary.json()
    assert len(data["positions"]) == 1
    assert float(data["total_invested"]) == pytest.approx(1025.0)
    assert data["positions"][0]["quantity"] == 100


@pytest.mark.asyncio
async def test_avg_price_after_two_buys(client: AsyncClient):
    token = await _register_and_token(client)
    portfolio = await client.post(
        "/api/portfolios/", json={"name": "FIIs"}, headers={"Authorization": f"Bearer {token}"}
    )
    pid = portfolio.json()["id"]
    asset = await _create_asset(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # Compra 1: 100 cotas a R$ 10,00
    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={"asset_id": asset["id"], "transaction_type": "BUY", "quantity": 100, "price": "10.00", "date": "2026-03-01"},
        headers=headers,
    )
    # Compra 2: 100 cotas a R$ 11,00
    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={"asset_id": asset["id"], "transaction_type": "BUY", "quantity": 100, "price": "11.00", "date": "2026-03-10"},
        headers=headers,
    )

    summary = await client.get(f"/api/portfolios/{pid}", headers=headers)
    pos = summary.json()["positions"][0]
    assert pos["quantity"] == 200
    # Preço médio esperado: (100*10 + 100*11) / 200 = 10,50
    assert float(pos["avg_price"]) == pytest.approx(10.50)


@pytest.mark.asyncio
async def test_sell_reduces_quantity(client: AsyncClient):
    token = await _register_and_token(client)
    portfolio = await client.post(
        "/api/portfolios/", json={"name": "FIIs"}, headers={"Authorization": f"Bearer {token}"}
    )
    pid = portfolio.json()["id"]
    asset = await _create_asset(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={"asset_id": asset["id"], "transaction_type": "BUY", "quantity": 100, "price": "10.00", "date": "2026-03-01"},
        headers=headers,
    )
    resp = await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={"asset_id": asset["id"], "transaction_type": "SELL", "quantity": 30, "price": "11.00", "date": "2026-03-15"},
        headers=headers,
    )
    assert resp.status_code == 201

    summary = await client.get(f"/api/portfolios/{pid}", headers=headers)
    assert summary.json()["positions"][0]["quantity"] == 70
