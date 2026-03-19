"""Modelo SQLAlchemy para ativos negociados (ações e FIIs)."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "ACAO" | "FII"
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    positions: Mapped[list["PortfolioAsset"]] = relationship(  # noqa: F821
        "PortfolioAsset", back_populates="asset"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="asset"
    )
