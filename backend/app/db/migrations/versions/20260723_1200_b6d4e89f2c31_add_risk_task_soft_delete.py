"""add risk assessment task soft delete

Revision ID: b6d4e89f2c31
Revises: a8f2c0d7e451
Create Date: 2026-07-23 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b6d4e89f2c31"
down_revision = "a8f2c0d7e451"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "risk_assessment_task",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "risk_assessment_task",
        sa.Column("deleted_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_risk_task_deleted_by_user",
        "risk_assessment_task",
        "user_account",
        ["deleted_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_risk_task_created_by_deleted_created",
        "risk_assessment_task",
        ["created_by", "deleted_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_task_created_by_deleted_created",
        table_name="risk_assessment_task",
    )
    op.drop_constraint(
        "fk_risk_task_deleted_by_user",
        "risk_assessment_task",
        type_="foreignkey",
    )
    op.drop_column("risk_assessment_task", "deleted_by_user_id")
    op.drop_column("risk_assessment_task", "deleted_at")
