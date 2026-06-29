"""add file parse task

Revision ID: 9b1f8a7c2d34
Revises: 36240c81e0d1
Create Date: 2026-06-29 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "9b1f8a7c2d34"
down_revision = "36240c81e0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_parse_task",
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=True),
        sa.Column("source_uri", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("reader_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_key.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_file_parse_task_created_by_created",
        "file_parse_task",
        ["created_by", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_file_parse_task_owner_created",
        "file_parse_task",
        ["owner_org_unit_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_file_parse_task_status_created",
        "file_parse_task",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("file_parse_task")
