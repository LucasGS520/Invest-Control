"""Implementa endpoints simples para verificar a saúde da aplicação."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Verifica o estado da API")
def read_health() -> HealthResponse:
    """Retorna um resumo mínimo para monitoramento local e integração futura."""

    # Mantemos os dados explícitos para facilitar observabilidade e smoke tests.
    return HealthResponse(
        status="ok",
        application=settings.app_name,
        environment=settings.app_env,
        version="0.1.0",
    )
