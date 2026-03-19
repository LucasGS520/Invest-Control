"""Modelo SQLAlchemy para proventos (dividendos, JCP, rendimentos)."""

from datetime import date

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dividend(Base):
    """Registra histórico de proventos pagos por um ativo.

    Usado para cálculo de DY histórico, calendário de proventos
    e motor de recomendação de aportes (FR1, FR4, FR5).
    """

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Valor pago por cota/ação
    value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    # Data em que o investidor precisa ter o ativo para receber o provento
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Data efetiva do pagamento (pode ser None se ainda não confirmada)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "DIVIDENDO" | "JCP" | "RENDIMENTO" | "AMORTIZACAO"
    dividend_type: Mapped[str] = mapped_column(String(20), nullable=False, default="DIVIDENDO")
