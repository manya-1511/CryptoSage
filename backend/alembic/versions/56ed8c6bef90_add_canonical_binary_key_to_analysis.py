"""add canonical binary key to analysis

Revision ID: 56ed8c6bef90
Revises: 613e0cd8d34f
Create Date: 2026-10-28 05:46:53.070757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56ed8c6bef90'
down_revision: Union[str, Sequence[str], None] = '613e0cd8d34f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis",
        sa.Column("binary_key", sa.String(length=1000), nullable=True),
    )
    op.create_unique_constraint(
        "uq_analysis_firmware_binary_key",
        "analysis",
        ["firmware_id", "binary_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_analysis_firmware_binary_key",
        "analysis",
        type_="unique",
    )
    op.drop_column("analysis", "binary_key")