"""Testes para registro, login e endpoint /me."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"name": "Lucas", "email": "lucas@test.com", "password": "senha123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "lucas@test.com"
    assert "access_token" in data["token"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"name": "Lucas", "email": "dup@test.com", "password": "senha123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400
    assert "E-mail" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"name": "Lucas", "email": "lucas@test.com", "password": "senha123"},
    )
    resp = await client.post(
        "/api/auth/login",
        data={"username": "lucas@test.com", "password": "senha123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"name": "Lucas", "email": "lucas@test.com", "password": "senha123"},
    )
    resp = await client.post(
        "/api/auth/login",
        data={"username": "lucas@test.com", "password": "errada"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={"name": "Lucas", "email": "lucas@test.com", "password": "senha123"},
    )
    token = reg.json()["token"]["access_token"]
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "lucas@test.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_and_login_with_long_password(client: AsyncClient):
    long_password = "A" * 80 + "!x9"

    reg = await client.post(
        "/api/auth/register",
        json={"name": "Long Pass", "email": "longpass@test.com", "password": long_password},
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/auth/login",
        data={"username": "longpass@test.com", "password": long_password},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()
