"""add contract review history soft delete

Revision ID: a8f2c0d7e451
Revises: f93a61d7c402
Create Date: 2026-07-23 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a8f2c0d7e451"
down_revision = "f93a61d7c402"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为合同审查最近工作记录增加逻辑删除审计字段。"""
    op.add_column(
        "contract_review_task",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "contract_review_task",
        sa.Column("deleted_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_contract_review_task_deleted_by_user",
        "contract_review_task",
        "user_account",
        ["deleted_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_contract_review_task_user_deleted_created",
        "contract_review_task",
        ["created_by", "deleted_at", "created_at"],
    )


def downgrade() -> None:
    """移除合同审查最近工作记录逻辑删除字段。"""
    op.drop_index(
        "ix_contract_review_task_user_deleted_created",
        table_name="contract_review_task",
    )
    op.drop_constraint(
        "fk_contract_review_task_deleted_by_user",
        "contract_review_task",
        type_="foreignkey",
    )
    op.drop_column("contract_review_task", "deleted_by_user_id")
    op.drop_column("contract_review_task", "deleted_at")
