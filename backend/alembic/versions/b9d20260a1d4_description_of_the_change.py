"""Description of the change

Revision ID: b9d20260a1d4
Revises: 7e5deeb8a645
Create Date: 2026-08-07 13:38:45.729975

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b9d20260a1d4"
down_revision: Union[str, Sequence[str], None] = "7e5deeb8a645"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add risk factors as JSONB.
    op.add_column(
        "analysis",
        sa.Column(
            "risk_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Add analysis status.
    op.add_column(
        "analysis",
        sa.Column(
            "analysis_status",
            sa.String(length=50),
            nullable=True,
        ),
    )

    # Convert the existing recommendation VARCHAR(500)
    # column into JSONB.
    #
    # to_jsonb(recommendation) safely converts existing text
    # values into JSONB strings.
    op.alter_column(
        "analysis",
        "recommendation",
        existing_type=sa.VARCHAR(length=500),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="to_jsonb(recommendation)",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Convert recommendation from JSONB back to VARCHAR(500).
    op.alter_column(
        "analysis",
        "recommendation",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.VARCHAR(length=500),
        existing_nullable=True,
        postgresql_using="recommendation::text",
    )

    # Remove analysis status.
    op.drop_column(
        "analysis",
        "analysis_status",
    )

    # Remove risk factors.
    op.drop_column(
        "analysis",
        "risk_factors",
    )