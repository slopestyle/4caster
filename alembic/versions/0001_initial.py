"""initial: forecast_card_cache

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_card_cache",
        sa.Column("location_id", sa.String(64), primary_key=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("consensus", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("forecast_card_cache")
