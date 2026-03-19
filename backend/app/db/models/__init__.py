"""Importa todos os modelos para que o Alembic detecte as tabelas via autogenerate."""

from app.db.models.asset import Asset
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.transaction import Transaction
from app.db.models.user import User

__all__ = ["User", "Portfolio", "Asset", "PortfolioAsset", "Transaction"]
