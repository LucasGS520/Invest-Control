"""Modelo SQLAlchemy para alertas inteligentes de investimento (FR8)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    """Alerta configurado pelo usuário para monitorar condições de mercado.

    Tipos suportados:
    - PRICE_BELOW  : preço atual abaixo de `threshold`
    - PRICE_ABOVE  : preço atual acima de `threshold`
    - BELOW_CEILING: ativo abaixo do preço-teto Barsi calculado
    - EX_DATE      : data ex-dividendo em `days_before_ex` dias ou menos
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Tipo do alerta
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Preço-alvo para PRICE_BELOW / PRICE_ABOVE
    threshold: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    # Dias de antecedência para EX_DATE
    days_before_ex: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Última vez que o alerta foi disparado (evita spam)
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
