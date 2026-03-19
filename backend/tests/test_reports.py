"""Testes para os Relatórios de Performance e Dividendos (FR7)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote


# ── Helpers ────────────────────────────────────────────────────────────────


async def _register_and_token(client: AsyncClient, email: str = "rep@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Rep User", "email": email, "password": "senha123"},
    )
    assert resp.status_code == 201
    return resp.json()["token"]["access_token"]


async def _setup_portfolio_with_position(
    client: AsyncClient,
    token: str,
    ticker: str = "MXRF11",
    qty: int = 100,
    price: float = 10.0,
) -> tuple[int, int]:
    """Cria carteira, ativo e compra. Retorna (portfolio_id, asset_id)."""
    resp_p = await client.post(
        "/api/portfolios/",
        json={"name": "Rep Portfolio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = resp_p.json()["id"]

    resp_a = await client.post(
        "/api/assets/",
        json={"ticker": ticker, "name": f"{ticker} Fundo", "asset_type": "FII"},
        headers={"Authorization": f"Bearer {token}"},
    )
    aid = resp_a.json()["id"]

    await client.post(
        f"/api/portfolios/{pid}/transactions",
        json={
            "asset_id": aid,
            "transaction_type": "BUY",
            "quantity": qty,
            "price": price,
            "date": str(date.today()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return pid, aid


# ── Testes de Performance ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_performance_unauthorized(client: AsyncClient):
    resp = await client.get("/api/reports/performance", params={"portfolio_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_performance_not_found(client: AsyncClient):
    token = await _register_and_token(client)
    resp = await client.get(
        "/api/reports/performance",
        params={"portfolio_id": 9999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_performance_empty_portfolio(client: AsyncClient):
    """Carteira sem posições: totais zerados."""
    token = await _register_and_token(client)
    resp_p = await client.post(
        "/api/portfolios/", json={"name": "Vazia"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = resp_p.json()["id"]

    resp = await client.get(
        "/api/reports/performance",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_invested"]) == 0.0
    assert data["positions"] == []


@pytest.mark.asyncio
async def test_performance_with_position(client: AsyncClient):
    """Compra de 100 cotas × R$ 10 → total_invested = 1000."""
    token = await _register_and_token(client)
    pid, _ = await _setup_portfolio_with_position(client, token, qty=100, price=10.0)

    resp = await client.get(
        "/api/reports/performance",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_invested"]) == pytest.approx(1000.0)
    assert len(data["positions"]) == 1
    assert data["positions"][0]["ticker"] == "MXRF11"


@pytest.mark.asyncio
async def test_performance_with_quote_shows_return(
    client: AsyncClient, db_session: AsyncSession
):
    """Com cotação acima do PM → retorno positivo."""
    token = await _register_and_token(client, email="rep2@test.com")
    pid, _ = await _setup_portfolio_with_position(client, token, qty=100, price=10.0)

    db_session.add(MarketQuote(ticker="MXRF11", price=Decimal("11.00")))
    await db_session.commit()

    resp = await client.get(
        "/api/reports/performance",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_return"]) == pytest.approx(100.0)
    assert float(data["total_return_pct"]) == pytest.approx(10.0)


# ── Testes de Renda de Dividendos ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_dividend_income_empty(client: AsyncClient):
    """Sem dividendos → total_12m = 0."""
    token = await _register_and_token(client, email="rep3@test.com")
    pid, _ = await _setup_portfolio_with_position(client, token)

    resp = await client.get(
        "/api/reports/dividend-income",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_12m"]) == 0.0
    assert len(data["monthly_income"]) == 12


@pytest.mark.asyncio
async def test_dividend_income_with_dividends(
    client: AsyncClient, db_session: AsyncSession
):
    """Dividendo de R$ 0.10 × 100 cotas = R$ 10 no mês."""
    token = await _register_and_token(client, email="rep4@test.com")
    pid, _ = await _setup_portfolio_with_position(client, token, qty=100)

    # Dividendo no mês atual
    this_month_ex = date.today().replace(day=10)
    if this_month_ex > date.today():
        this_month_ex = date.today() - timedelta(days=5)

    db_session.add(
        Dividend(
            ticker="MXRF11",
            value=Decimal("0.10"),
            ex_date=this_month_ex,
            dividend_type="RENDIMENTO",
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/reports/dividend-income",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 100 cotas × 0.10 = 10.00
    assert float(data["total_12m"]) == pytest.approx(10.0)


# ── Testes de Projeções ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_projections_no_dividends(client: AsyncClient):
    """Sem dividendos → renda projetada zero."""
    token = await _register_and_token(client, email="rep5@test.com")
    pid, _ = await _setup_portfolio_with_position(client, token)

    resp = await client.get(
        "/api/reports/projections",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["projected_annual_income"]) == 0.0
    assert data["avg_dy"] is None


@pytest.mark.asyncio
async def test_projections_with_dividends(
    client: AsyncClient, db_session: AsyncSession
):
    """Com dividendos históricos e cotação → DY e projeção calculados."""
    token = await _register_and_token(client, email="rep6@test.com")
    pid, _ = await _setup_portfolio_with_position(client, token, qty=100, price=10.0)

    db_session.add(MarketQuote(ticker="MXRF11", price=Decimal("10.00")))

    # 12 dividendos mensais de R$ 0.10 cada
    for month in range(1, 13):
        ex = date.today() - timedelta(days=(12 - month) * 30)
        db_session.add(
            Dividend(
                ticker="MXRF11",
                value=Decimal("0.10"),
                ex_date=ex,
                dividend_type="RENDIMENTO",
            )
        )
    await db_session.commit()

    resp = await client.get(
        "/api/reports/projections",
        params={"portfolio_id": pid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 12 × 0.10 × 100 = 120
    assert float(data["projected_annual_income"]) == pytest.approx(120.0, abs=5.0)
    assert float(data["projected_monthly_income"]) == pytest.approx(10.0, abs=1.0)
    assert data["avg_dy"] is not None


@pytest.mark.asyncio
async def test_reports_portfolio_isolation(client: AsyncClient):
    """Usuário B não acessa relatórios da carteira de A."""
    token_a = await _register_and_token(client, email="riso_a@test.com")
    resp_p = await client.post(
        "/api/portfolios/", json={"name": "A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    pid_a = resp_p.json()["id"]

    token_b = await _register_and_token(client, email="riso_b@test.com")
    for endpoint in ["performance", "dividend-income", "projections"]:
        resp = await client.get(
            f"/api/reports/{endpoint}",
            params={"portfolio_id": pid_a},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404, f"Expected 404 on /reports/{endpoint}"
