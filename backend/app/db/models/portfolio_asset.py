"""Modelo SQLAlchemy para posições consolidadas em uma carteira."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PortfolioAsset(Base):
    """Representa a posição consolidada de um ativo em uma carteira.

    O avg_price é recalculado a cada transação de compra (BUY).
    Em vendas (SELL), apenas a quantity é reduzida.
    """

    __tablename__ = "portfolio_assets"
    __table_args__ = (UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_asset"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="positions")  # noqa: F821
    asset: Mapped["Asset"] = relationship("Asset", back_populates="positions")  # noqa: F821
