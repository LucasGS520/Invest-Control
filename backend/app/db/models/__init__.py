"""Importa todos os modelos para que o Alembic detecte as tabelas via autogenerate."""

from app.db.models.alert import Alert
from app.db.models.asset import Asset
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.transaction import Transaction
from app.db.models.user import User

__all__ = [
    "Alert",
    "Asset",
    "Dividend",
    "MarketQuote",
    "Portfolio",
    "PortfolioAsset",
    "Transaction",
    "User",
]
