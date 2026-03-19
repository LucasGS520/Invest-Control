"""add_alert_table

Revision ID: 3a9f2e8d1c05
Revises: 8f2a1d9e4b7c
Create Date: 2026-03-19

Adiciona tabela de alertas inteligentes da Fase 4 (FR8).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3a9f2e8d1c05"
down_revision: Union[str, None] = "8f2a1d9e4b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("days_before_ex", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_id", "alerts", ["id"])
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_ticker", "alerts", ["ticker"])


def downgrade() -> None:
    op.drop_table("alerts")
