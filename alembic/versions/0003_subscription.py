"""subscription: подписки на изменения (US-SUB-1)

Revision ID: 0003_subscription
Revises: 0002_forecast_history
Create Date: 2026-07-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_subscription"
down_revision: Union[str, None] = "0002_forecast_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("location_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscription_location", "subscription", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_subscription_location", table_name="subscription")
    op.drop_table("subscription")
