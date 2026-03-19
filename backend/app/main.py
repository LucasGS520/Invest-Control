"""Ponto de entrada da aplicação FastAPI do InvestControl."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.alerts import router as alerts_router
from app.api.routes.aporte import router as aporte_router
from app.api.routes.assets import router as assets_router
from app.api.routes.auth import router as auth_router
from app.api.routes.calendar import router as calendar_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.portfolios import router as portfolios_router
from app.api.routes.transactions import router as transactions_router
from app.core.config import settings
from app.tasks.update_quotes import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Gerencia o ciclo de vida da aplicação: inicia e para o scheduler."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    debug=settings.app_debug,
    lifespan=lifespan,
    description=(
        "API do InvestControl — plataforma de aportes sob demanda com foco em dividendos. "
        "Inclui autenticação JWT, gestão de carteiras, dados de mercado (brapi.dev), "
        "DY histórico e preço-teto Barsi."
    ),
)

# Prefixo /api em todos os routers para facilitar versionamento futuro.
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(portfolios_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(assets_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(aporte_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")


@app.get("/", tags=["Root"], summary="Resumo da API")
def read_root() -> dict[str, str]:
    """Expõe uma mensagem curta para identificar o serviço em execução."""
    return {
        "name": settings.app_name,
        "version": "0.5.0",
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/api/health",
    }
