"""Ponto de entrada da aplicação FastAPI do InvestControl."""

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.app_debug,
    description=(
        "API inicial do InvestControl para dar suporte ao MVP de aporte sob demanda, "
        "carteiras e integrações futuras."
    ),
)

# O prefixo /api facilita versionamento e organização quando o domínio crescer.
app.include_router(health_router, prefix="/api")


@app.get("/", tags=["Root"], summary="Resumo da API")
def read_root() -> dict[str, str]:
    """Expõe uma mensagem curta para identificar o serviço em execução."""

    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/api/health",
    }
