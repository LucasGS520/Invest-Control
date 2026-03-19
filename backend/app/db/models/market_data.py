"""Modelo SQLAlchemy para cotações de mercado com cache."""

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketQuote(Base):
    """Armazena a cotação mais recente de cada ativo.

    Usada como cache para evitar chamadas excessivas à API externa.
    A coluna updated_at permite checar a 'idade' dos dados (NFR7).
    """

    __tablename__ = "market_quotes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    # Variação percentual no dia (ex: -1.25)
    change_percent: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    # Volume negociado no dia
    volume: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
