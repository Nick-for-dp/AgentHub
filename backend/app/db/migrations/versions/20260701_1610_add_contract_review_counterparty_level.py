"""add contract review execution inputs

Revision ID: d41f7a9c2b80
Revises: c7a92e54f6b1
Create Date: 2026-07-01 16:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d41f7a9c2b80"
down_revision = "c7a92e54f6b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为合同审查任务记录异步执行所需的业务输入。"""
    op.add_column(
        "contract_review_task",
        sa.Column(
            "contract_type",
            sa.String(length=50),
            nullable=False,
            server_default="warehouse",
        ),
    )
    op.add_column(
        "contract_review_task",
        sa.Column(
            "counterparty_level",
            sa.String(length=16),
            nullable=False,
            server_default="A1",
        ),
    )
    op.alter_column("contract_review_task", "contract_type", server_default=None)
    op.alter_column("contract_review_task", "counterparty_level", server_default=None)


def downgrade() -> None:
    """删除合同审查任务执行输入字段。"""
    op.drop_column("contract_review_task", "counterparty_level")
    op.drop_column("contract_review_task", "contract_type")
