"""Centraliza as configurações base da aplicação FastAPI."""

from pydantic import Field
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
    price_providers_order: list[str] = Field(
        default_factory=lambda: ["yfinance", "twelvedata", "brapi"]
    )
    dividend_providers_order: list[str] = Field(
        default_factory=lambda: ["statusinvest", "fundamentus", "brapi"]
    )
    twelvedata_api_key: str = ""
    twelvedata_base_url: str = "https://api.twelvedata.com"
    market_data_concurrency: int = 5
    provider_timeouts_seconds: dict[str, float] = Field(
        default_factory=lambda: {
            "default": 10.0,
            "yfinance": 15.0,
            "twelvedata": 10.0,
            "statusinvest": 10.0,
            "fundamentus": 10.0,
            "b3": 20.0,
        }
    )
    # CORS: origens permitidas para o frontend (por padrão Vite dev)
    allowed_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
