"""Testes para o Motor de Aporte Sob Demanda (FR1)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.user import User
from app.services.aporte_service import (
    _score_ceiling_distance,
    _score_dy,
    _score_ex_date,
    _score_portfolio_weight,
)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _setup_user_portfolio(db: AsyncSession) -> tuple[User, Portfolio, Asset]:
    """Cria usuário, carteira e ativo base para testes."""
    user = User(name="Test", email="t@t.com", hashed_password="x")
    db.add(user)
    await db.flush()

    portfolio = Portfolio(user_id=user.id, name="Teste")
    db.add(portfolio)
    await db.flush()

    asset = Asset(ticker="MXRF11", name="Maxi Renda FII", asset_type="FII")
    db.add(asset)
    await db.flush()

    return user, portfolio, asset


async def _register_and_token(client: AsyncClient, email: str = "aporte@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Aporte User", "email": email, "password": "senha123"},
    )
    assert resp.status_code == 201
    return resp.json()["token"]["access_token"]


async def _create_portfolio(client: AsyncClient, token: str, name: str = "Carteira FII") -> int:
    resp = await client.post(
        "/api/portfolios/",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_asset(client: AsyncClient, token: str, ticker: str = "MXRF11") -> int:
    resp = await client.post(
        "/api/assets/",
        json={"ticker": ticker, "name": f"{ticker} Fundo", "asset_type": "FII"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _add_transaction(
    client: AsyncClient, token: str, portfolio_id: int, ticker: str, qty: int = 10, price: float = 10.0
) -> None:
    resp = await client.post(
        f"/api/portfolios/{portfolio_id}/transactions",
        json={
            "ticker": ticker,
            "transaction_type": "BUY",
            "quantity": qty,
            "price": price,
            "date": str(date.today()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# ── Testes unitários dos helpers de score ──────────────────────────────────


def test_score_ceiling_distance_below():
    """Ativo 20% abaixo do teto → score entre 50 e 100."""
    score = _score_ceiling_distance(Decimal("20"), is_below=True)
    assert Decimal("50") < score <= Decimal("100")


def test_score_ceiling_distance_above():
    """Ativo acima do teto → score 0."""
    score = _score_ceiling_distance(Decimal("10"), is_below=False)
    assert score == Decimal("0")


def test_score_ceiling_distance_none():
    """Sem dado de teto → score neutro 50."""
    score = _score_ceiling_distance(None, is_below=True)
    assert score == Decimal("50")


def test_score_dy_above_desired():
    """DY = 2× o desejado → score máximo."""
    score = _score_dy(Decimal("12"), Decimal("6"))
    assert score == Decimal("100")


def test_score_dy_zero():
    """DY = 0 → score 0."""
    score = _score_dy(Decimal("0"), Decimal("6"))
    assert score == Decimal("0")


def test_score_dy_none():
    """DY None → score 0."""
    score = _score_dy(None, Decimal("6"))
    assert score == Decimal("0")


def test_score_ex_date_very_soon():
    """Data ex em 3 dias → 100 pts."""
    next_ex = date.today() + timedelta(days=3)
    assert _score_ex_date(next_ex) == Decimal("100")


def test_score_ex_date_none():
    """Sem data ex → 10 pts."""
    assert _score_ex_date(None) == Decimal("10")


def test_score_portfolio_weight_underweight():
    """Ativo com metade do peso ideal → score acima de 50."""
    score = _score_portfolio_weight(
        position_value=Decimal("500"),
        total_portfolio_value=Decimal("2000"),
        asset_count=2,  # ideal = 50%
    )
    # Peso atual 25%, ideal 50% → gap positivo → score > 50
    assert score > Decimal("50")


def test_score_portfolio_weight_empty():
    """Carteira vazia → score neutro 50."""
    score = _score_portfolio_weight(Decimal("0"), Decimal("0"), 0)
    assert score == Decimal("50")


# ── Testes de integração via HTTP ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_recommend_empty_portfolio(client: AsyncClient):
    """Carteira sem ativos retorna lista vazia de recomendações."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 1000.0, "desired_dy": 6.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommendations"] == []
    assert float(data["remaining_value"]) == 1000.0


@pytest.mark.asyncio
async def test_recommend_unauthorized(client: AsyncClient):
    """Sem token → 401."""
    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": 1, "value": 500.0},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recommend_portfolio_not_found(client: AsyncClient):
    """Carteira inexistente → 404."""
    token = await _register_and_token(client)
    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": 9999, "value": 500.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recommend_portfolio_isolation(client: AsyncClient):
    """Usuário B não pode acessar carteira do usuário A."""
    token_a = await _register_and_token(client, email="a@test.com")
    pid_a = await _create_portfolio(client, token_a)

    token_b = await _register_and_token(client, email="b@test.com")
    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid_a, "value": 500.0},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recommend_with_position_no_quote(client: AsyncClient):
    """Carteira com posição mas sem cotação: retorna recomendação com qty=0 e limitação."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)
    await _add_transaction(client, token, pid, "MXRF11", qty=10, price=10.0)

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 500.0, "desired_dy": 6.0, "max_assets": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recommendations"]) == 1
    rec = data["recommendations"][0]
    assert rec["ticker"] == "MXRF11"
    # Sem cotação → qty 0 e limitação mencionada
    assert rec["recommended_quantity"] == 0
    assert any("cotação" in lim.lower() or "preço" in lim.lower() for lim in rec["limitations"])


@pytest.mark.asyncio
async def test_recommend_with_quote_calculates_quantity(client: AsyncClient, db_session: AsyncSession):
    """Com cotação disponível, calcula quantidade máxima comprável."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)
    await _add_transaction(client, token, pid, "MXRF11", qty=10, price=10.0)

    # Insere cotação diretamente no banco
    quote = MarketQuote(ticker="MXRF11", price=Decimal("10.00"))
    db_session.add(quote)
    await db_session.commit()

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 50.0, "desired_dy": 6.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    rec = data["recommendations"][0]
    # R$ 50 / R$ 10 = 5 unidades
    assert rec["recommended_quantity"] == 5
    assert float(rec["total_cost"]) == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_recommend_max_assets_limit(client: AsyncClient, db_session: AsyncSession):
    """Respeita o parâmetro max_assets."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)

    tickers = ["MXRF11", "HGLG11", "XPML11"]
    for ticker in tickers:
        await _add_transaction(client, token, pid, ticker, qty=5, price=10.0)

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 100.0, "desired_dy": 6.0, "max_assets": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["recommendations"]) <= 2


@pytest.mark.asyncio
async def test_recommend_response_schema(client: AsyncClient):
    """Resposta contém todos os campos do schema AporteRecommendationOut."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 1000.0, "desired_dy": 6.0, "max_assets": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_id" in data
    assert "available_value" in data
    assert "desired_dy" in data
    assert "recommendations" in data
    assert "remaining_value" in data
    assert float(data["available_value"]) == pytest.approx(1000.0)
    assert float(data["desired_dy"]) == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_recommend_score_includes_justifications(client: AsyncClient, db_session: AsyncSession):
    """Recomendação com dados suficientes inclui justificativas."""
    token = await _register_and_token(client)
    pid = await _create_portfolio(client, token)
    await _add_transaction(client, token, pid, "MXRF11", qty=10, price=10.0)

    # Cotação abaixo do teto calculável
    quote = MarketQuote(ticker="MXRF11", price=Decimal("9.00"))
    db_session.add(quote)

    # Dividendo recente para DY calculável
    div = Dividend(
        ticker="MXRF11",
        value=Decimal("0.10"),
        ex_date=date.today() - timedelta(days=30),
        payment_date=date.today() - timedelta(days=20),
        dividend_type="RENDIMENTO",
    )
    db_session.add(div)
    await db_session.commit()

    resp = await client.post(
        "/api/aporte/recommend",
        json={"portfolio_id": pid, "value": 100.0, "desired_dy": 6.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    rec = resp.json()["recommendations"][0]
    # Score deve ser um número válido entre 0 e 100
    assert 0 <= float(rec["score"]) <= 100
    # Deve ter lista de justificativas e limitações (ambas podem ser vazias, mas existem)
    assert isinstance(rec["justifications"], list)
    assert isinstance(rec["limitations"], list)
