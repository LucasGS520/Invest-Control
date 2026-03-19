"""Centraliza as configurações base da aplicação FastAPI."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define as variáveis de ambiente usadas pela API do MVP."""

    app_name: str = "InvestControl API"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql://investcontrol:investcontrol@postgres:5432/investcontrol"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
