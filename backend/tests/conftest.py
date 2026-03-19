"""Fixtures compartilhadas pelos testes do InvestControl."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Banco SQLite em memória para testes (sem dependência de PostgreSQL)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSession = async_sessionmaker(bind=_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Cria e destrói as tabelas a cada teste para garantir isolamento."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with _TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Cliente HTTP que usa o banco de testes via override de dependência."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
