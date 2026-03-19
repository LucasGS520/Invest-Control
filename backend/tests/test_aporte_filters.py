"""Testes para os filtros de personalização do Motor de Aporte (FR6)."""

from datetime import date

import pytest
from httpx import AsyncClient


async def _register_and_token(client: AsyncClient, email: str = "fr6@test.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"name": "FR6 User", "email": email, "password": "senha123"},
    )
    assert resp.status_code == 201
    return resp.json()["token"]["access_token"]


async def _setup_mixed_portfolio(client: AsyncClient, token: str) -> int:
    """Cria carteira com 1 FII e 1 ACAO."""
    resp_p = await client.post(
        "/api/portfolios/",
        json={"name": "Mista"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = resp_p.json()["id"]

    # FII
    resp_fii = await client.post(
        "/api/assets/",
        json={"ticker": "MXRF11", "name": "Maxi Renda", "asset_type": "FII"},
        headers={"Authorization": f"Bearer {token}"},
    )
    aid_fii = resp_fii.json()["id"]

    # ACAO
    resp_acao = await client.post(
        "/api/assets/",
        json={"ticker": "ITUB4", "name": "Itau Unibanco", "asset_type": "ACAO"},
        headers={"Authorization": f"Bearer {token}"},
    )
    aid_acao = resp_acao.json()["id"]

    for aid in [aid_fii, aid_acao]:
        await client.post(
            f"/api/portfolios/{pid}/transactions",
            json={
                "asset_id": aid,
                "transaction_type": "BUY",
                "quantity": 10,
                "price": 10.0,
                "date": str(date.today()),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    return pid


@pytest.mark.asyncio
async def test_filter_by_asset_type_fii(client: AsyncClient):
    """Filtro FII exclui ações da recomendação."""
    token = await _register_and_token(client)
    pid = await _setup_mixed_portfolio(client, token)

    resp = await client.post(
        "/api/aporte/recommend",
        json={
            "portfolio_id": pid,
            "value": 100.0,
            "desired_dy": 6.0,
            "asset_type_filter": "FII",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert all(r["asset_type"] == "FII" for r in recs)


@pytest.mark.asyncio
async def test_filter_by_asset_type_acao(client: AsyncClient):
    """Filtro ACAO exclui FIIs da recomendação."""
    token = await _register_and_token(client, email="fr6b@test.com")
    pid = await _setup_mixed_portfolio(client, token)

    resp = await client.post(
        "/api/aporte/recommend",
        json={
            "portfolio_id": pid,
            "value": 100.0,
            "desired_dy": 6.0,
            "asset_type_filter": "ACAO",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert all(r["asset_type"] == "ACAO" for r in recs)


@pytest.mark.asyncio
async def test_filter_returns_empty_when_no_match(client: AsyncClient):
    """Filtro que exclui todos os ativos retorna lista vazia."""
    token = await _register_and_token(client, email="fr6c@test.com")
    pid = await _setup_mixed_portfolio(client, token)

    # Setor inexistente — retorna vazio
    resp = await client.post(
        "/api/aporte/recommend",
        json={
            "portfolio_id": pid,
            "value": 100.0,
            "desired_dy": 6.0,
            "sector_filter": ["Setor Inexistente XYZ"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []
