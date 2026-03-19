"""Ponto de entrada da aplicação FastAPI do InvestControl."""

from fastapi import FastAPI

from app.api.routes.assets import router as assets_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.portfolios import router as portfolios_router
from app.api.routes.transactions import router as transactions_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    debug=settings.app_debug,
    description=(
        "API do InvestControl — plataforma de aportes sob demanda com foco em dividendos. "
        "Inclui autenticação JWT, gestão de carteiras e integração com dados de mercado."
    ),
)

# Prefixo /api em todos os routers para facilitar versionamento futuro.
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(portfolios_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(assets_router, prefix="/api")


@app.get("/", tags=["Root"], summary="Resumo da API")
def read_root() -> dict[str, str]:
    """Expõe uma mensagem curta para identificar o serviço em execução."""
    return {
        "name": settings.app_name,
        "version": "0.2.0",
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/api/health",
    }
