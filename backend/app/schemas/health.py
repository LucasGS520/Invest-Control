"""Schemas usados na resposta do endpoint de saúde da API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Representa o estado básico da aplicação durante o bootstrap do MVP."""

    status: str
    application: str
    environment: str
    version: str
