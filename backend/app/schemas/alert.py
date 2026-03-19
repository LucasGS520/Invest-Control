"""Schemas Pydantic para Alertas Inteligentes (FR8)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AlertType = Literal["PRICE_BELOW", "PRICE_ABOVE", "BELOW_CEILING", "EX_DATE"]


class AlertCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    alert_type: AlertType
    threshold: Decimal | None = Field(
        default=None,
        description="Preço-alvo para PRICE_BELOW / PRICE_ABOVE",
    )
    days_before_ex: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description="Dias de antecedência para alerta de EX_DATE",
    )

    @model_validator(mode="after")
    def validate_fields(self) -> "AlertCreate":
        if self.alert_type in ("PRICE_BELOW", "PRICE_ABOVE") and self.threshold is None:
            raise ValueError(f"threshold é obrigatório para o tipo {self.alert_type}")
        if self.alert_type == "EX_DATE" and self.days_before_ex is None:
            raise ValueError("days_before_ex é obrigatório para o tipo EX_DATE")
        return self


class AlertUpdate(BaseModel):
    is_active: bool | None = None
    threshold: Decimal | None = None
    days_before_ex: int | None = Field(default=None, ge=1, le=90)


class AlertOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    ticker: str
    alert_type: str
    threshold: Decimal | None
    days_before_ex: int | None
    is_active: bool
    triggered_at: datetime | None
    created_at: datetime
