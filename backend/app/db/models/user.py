"""Modelo SQLAlchemy para usuários da plataforma."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Preferências: {"desired_dy": 6.0, "sectors": ["FII"], "target_allocation": {}}
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    portfolios: Mapped[list["Portfolio"]] = relationship(  # noqa: F821
        "Portfolio", back_populates="user", cascade="all, delete-orphan"
    )
