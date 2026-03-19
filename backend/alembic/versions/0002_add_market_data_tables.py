"""add_market_data_tables

Revision ID: 8f2a1d9e4b7c
Revises: 533c7be2c60d
Create Date: 2026-03-19

Adiciona tabelas de dados de mercado da Fase 2:
  - market_quotes: cache de cotações com timestamp de atualização
  - dividends: histórico de proventos por ativo
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8f2a1d9e4b7c"
down_revision: Union[str, None] = "533c7be2c60d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── market_quotes ───────────────────────────────────────────────────────
    op.create_table(
        "market_quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("change_percent", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("volume", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_quotes_id", "market_quotes", ["id"])
    op.create_index("ix_market_quotes_ticker", "market_quotes", ["ticker"], unique=True)

    # ── dividends ────────────────────────────────────────────────────────────
    op.create_table(
        "dividends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("dividend_type", sa.String(length=20), nullable=False, server_default="DIVIDENDO"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dividends_id", "dividends", ["id"])
    op.create_index("ix_dividends_ticker", "dividends", ["ticker"])


def downgrade() -> None:
    op.drop_table("dividends")
    op.drop_table("market_quotes")
