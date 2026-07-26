"""forecast_history: эволюция прогноза (US-HIST-1)

Revision ID: 0002_forecast_history
Revises: 0001_initial
Create Date: 2026-07-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_forecast_history"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_history",
        sa.Column("location_id", sa.String(64), primary_key=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("valid_date", sa.Date(), primary_key=True),
        sa.Column("p10", sa.Float(), nullable=False),
        sa.Column("p50", sa.Float(), nullable=False),
        sa.Column("p90", sa.Float(), nullable=False),
        sa.Column("pop", sa.Float(), nullable=False),
        sa.Column("hil_level", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_forecast_history_loc_date",
        "forecast_history",
        ["location_id", "valid_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_history_loc_date", table_name="forecast_history")
    op.drop_table("forecast_history")
