"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # firmwares table
    op.create_table(
        "firmwares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_extension", sa.String(10), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("md5_hash", sa.String(32), nullable=True),
        sa.Column("architecture", sa.String(64), nullable=True),
        sa.Column("endianness", sa.String(16), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("vendor", sa.String(128), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "validating", "valid", "invalid",
                "extracting", "extracted", "failed",
                name="firmwarestatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_firmwares_id", "firmwares", ["id"])
    op.create_index("ix_firmwares_sha256_hash", "firmwares", ["sha256_hash"])

    # extraction_results table
    op.create_table(
        "extraction_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("firmware_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_path", sa.String(512), nullable=True),
        sa.Column("tool_used", sa.String(64), nullable=False, server_default="binwalk"),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="extractionstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("scan_results", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("file_tree", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("entropy_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("component_summary", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("total_files_extracted", sa.Integer(), server_default="0"),
        sa.Column("total_size_extracted", sa.BigInteger(), server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["firmware_id"], ["firmwares.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extraction_results_id", "extraction_results", ["id"])


def downgrade() -> None:
    op.drop_table("extraction_results")
    op.drop_table("firmwares")
    op.execute("DROP TYPE IF EXISTS firmwarestatus")
    op.execute("DROP TYPE IF EXISTS extractionstatus")