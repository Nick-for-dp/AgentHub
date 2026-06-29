"""add contract review task

Revision ID: c7a92e54f6b1
Revises: 9b1f8a7c2d34
Create Date: 2026-06-29 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c7a92e54f6b1"
down_revision = "9b1f8a7c2d34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建合同审查任务表及查询索引。"""
    op.create_table(
        "contract_review_task",
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=True),
        sa.Column("agent_code", sa.String(length=100), nullable=False),
        sa.Column("file_parse_task_id", sa.String(length=36), nullable=False),
        sa.Column("rule_set_version", sa.String(length=100), nullable=True),
        sa.Column("callback_metadata", sa.JSON(), nullable=False),
        sa.Column("invocation_record_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_key.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["file_parse_task_id"], ["file_parse_task.id"]),
        sa.ForeignKeyConstraint(["invocation_record_id"], ["agent_invocation_record.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contract_review_task_api_key_created",
        "contract_review_task",
        ["api_key_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_contract_review_task_created_by_created",
        "contract_review_task",
        ["created_by", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_contract_review_task_file_parse",
        "contract_review_task",
        ["file_parse_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_contract_review_task_owner_created",
        "contract_review_task",
        ["owner_org_unit_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_contract_review_task_status_created",
        "contract_review_task",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """删除合同审查任务表。"""
    op.drop_table("contract_review_task")
