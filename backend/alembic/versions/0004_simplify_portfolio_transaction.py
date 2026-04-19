"""simplify_portfolio_transaction

Revision ID: 4b1c3d7e2f09
Revises: 3a9f2e8d1c05
Create Date: 2026-04-18

Fase 2: adiciona objective/currency em portfolios e fees em transactions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4b1c3d7e2f09"
down_revision: Union[str, None] = "3a9f2e8d1c05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("objective", sa.String(200), nullable=True))
    op.add_column(
        "portfolios",
        sa.Column("currency", sa.String(10), nullable=False, server_default="BRL"),
    )
    op.add_column("transactions", sa.Column("fees", sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "fees")
    op.drop_column("portfolios", "currency")
    op.drop_column("portfolios", "objective")
