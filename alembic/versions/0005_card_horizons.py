"""forecast_card_cache.horizons: надёжность по горизонтам 1/3/7/14 (§10.6.3)

Revision ID: 0005_card_horizons
Revises: 0004_archive_daily
Create Date: 2026-09-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_card_horizons"
down_revision: Union[str, None] = "0004_archive_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: карточки прошлых прогонов остаются валидными и без горизонтов,
    # следующий цикл конвейера (6×/сутки) их дозаполнит.
    op.add_column(
        "forecast_card_cache",
        sa.Column("horizons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("forecast_card_cache", "horizons")
