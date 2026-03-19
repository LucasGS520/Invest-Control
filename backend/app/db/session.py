"""Configuração da sessão assíncrona do SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Converte a URL para o driver assíncrono (asyncpg)
_async_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

engine = create_async_engine(
    _async_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI que fornece uma sessão de banco de dados por requisição."""
    async with AsyncSessionLocal() as session:
        yield session
