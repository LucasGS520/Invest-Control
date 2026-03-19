"""Centraliza as configurações base da aplicação FastAPI."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define as variáveis de ambiente usadas pela API."""

    # Aplicação
    app_name: str = "InvestControl API"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Banco de dados
    database_url: str = "postgresql://investcontrol:investcontrol@postgres:5432/investcontrol"

    # Segurança / JWT
    secret_key: str = "mude-esta-chave-em-producao"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 horas

    # Integração de dados de mercado (brapi.dev)
    brapi_token: str = ""
    market_data_cache_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
