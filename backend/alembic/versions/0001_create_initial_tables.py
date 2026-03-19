"""create_initial_tables

Revision ID: 533c7be2c60d
Revises:
Create Date: 2026-03-19

Cria as tabelas do domínio core da Fase 1:
  - users
  - portfolios
  - assets
  - portfolio_assets
  - transactions
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "533c7be2c60d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── assets ─────────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("asset_type", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_id", "assets", ["id"])
    op.create_index("ix_assets_ticker", "assets", ["ticker"], unique=True)

    # ── portfolios ─────────────────────────────────────────────────────────
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolios_id", "portfolios", ["id"])

    # ── portfolio_assets ────────────────────────────────────────────────────
    op.create_table(
        "portfolio_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_price", sa.Numeric(precision=12, scale=4), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_asset"),
    )
    op.create_index("ix_portfolio_assets_id", "portfolio_assets", ["id"])

    # ── transactions ────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_id", "transactions", ["id"])
    op.create_index("ix_transactions_portfolio_id", "transactions", ["portfolio_id"])
    op.create_index("ix_transactions_asset_id", "transactions", ["asset_id"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("portfolio_assets")
    op.drop_table("portfolios")
    op.drop_table("assets")
    op.drop_table("users")
