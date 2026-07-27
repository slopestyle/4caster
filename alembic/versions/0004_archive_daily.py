"""archive_daily: архив суточных осадков по реанализу (задача 1.7)

Revision ID: 0004_archive_daily
Revises: 0003_subscription
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_archive_daily"
down_revision: Union[str, None] = "0003_subscription"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "archive_daily",
        sa.Column("location_id", sa.String(64), primary_key=True),
        sa.Column("valid_date", sa.Date(), primary_key=True),
        sa.Column("precip_mm", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
    )
    # Климатология считается срезами «все точки за месяц» — индекс по дате.
    op.create_index("ix_archive_daily_valid_date", "archive_daily", ["valid_date"])


def downgrade() -> None:
    op.drop_index("ix_archive_daily_valid_date", table_name="archive_daily")
    op.drop_table("archive_daily")
