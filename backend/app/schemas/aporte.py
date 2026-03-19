"""Schemas Pydantic para o motor de Aporte Sob Demanda (FR1)."""

from decimal import Decimal

from pydantic import BaseModel, Field


class AporteRequest(BaseModel):
    portfolio_id: int
    value: Decimal = Field(..., gt=0, description="Valor disponível para o aporte em R$")
    desired_dy: Decimal = Field(
        default=Decimal("6.0"),
        gt=0,
        description="DY mínimo desejado para cálculo do preço-teto Barsi (%)",
    )
    max_assets: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de ativos na lista de recomendações",
    )


class RecommendationItem(BaseModel):
    ticker: str
    asset_name: str
    asset_type: str

    # Preço e quantidade
    current_price: Decimal | None
    recommended_quantity: int
    total_cost: Decimal | None

    # Análise de valor
    barsi_ceiling: Decimal | None
    ceiling_distance_pct: Decimal | None
    is_below_ceiling: bool

    # Dividend Yield
    current_dy: Decimal | None

    # Score e justificativas
    score: Decimal
    justifications: list[str]
    limitations: list[str]


class AporteRecommendationOut(BaseModel):
    portfolio_id: int
    available_value: Decimal
    desired_dy: Decimal
    recommendations: list[RecommendationItem]
    remaining_value: Decimal
