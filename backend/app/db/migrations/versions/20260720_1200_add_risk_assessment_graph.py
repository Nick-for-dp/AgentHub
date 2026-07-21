"""add risk assessment graph and original filename

Revision ID: f93a61d7c402
Revises: d41f7a9c2b80
Create Date: 2026-07-20 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f93a61d7c402"
down_revision = "d41f7a9c2b80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "file_parse_task",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "risk_assessment_task",
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=True),
        sa.Column("agent_code", sa.String(length=100), nullable=False),
        sa.Column("business_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("graph_thread_id", sa.String(length=100), nullable=True),
        sa.Column("current_checkpoint_id", sa.String(length=100), nullable=True),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False),
        sa.Column("current_node", sa.String(length=100), nullable=True),
        sa.Column("invocation_record_id", sa.String(length=36), nullable=True),
        sa.Column("versions", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_key.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["invocation_record_id"], ["agent_invocation_record.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_task_owner_created",
        "risk_assessment_task",
        ["owner_org_unit_id", "created_at"],
    )
    op.create_index(
        "ix_risk_task_created_by_created",
        "risk_assessment_task",
        ["created_by", "created_at"],
    )
    op.create_index(
        "ix_risk_task_status_created",
        "risk_assessment_task",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_risk_task_graph_thread",
        "risk_assessment_task",
        ["graph_thread_id"],
    )
    op.create_table(
        "risk_assessment_document",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("file_parse_task_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_document_type", sa.String(length=50), nullable=False),
        sa.Column("document_order", sa.Integer(), nullable=False),
        sa.Column("type_validation_status", sa.String(length=32), nullable=False),
        sa.Column("type_validation_warnings", sa.JSON(), nullable=False),
        sa.Column("extraction_snapshot", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_parse_task_id"], ["file_parse_task.id"]),
        sa.ForeignKeyConstraint(
            ["task_id"], ["risk_assessment_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "file_parse_task_id", name="uq_risk_document_task_file"
        ),
    )
    op.create_index(
        "ix_risk_document_task_order",
        "risk_assessment_document",
        ["task_id", "document_order"],
    )
    op.create_index(
        "ix_risk_document_file_parse",
        "risk_assessment_document",
        ["file_parse_task_id"],
    )
    op.create_table(
        "risk_review_event",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("review_item_id", sa.String(length=100), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_code", sa.String(length=100), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user_account.id"]),
        sa.ForeignKeyConstraint(
            ["task_id"], ["risk_assessment_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_review_task_created", "risk_review_event", ["task_id", "created_at"]
    )
    op.create_index(
        "ix_risk_review_actor_created",
        "risk_review_event",
        ["actor_user_id", "created_at"],
    )
    op.create_table(
        "risk_graph_checkpoint",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=100), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("next_node", sa.String(length=100), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["risk_assessment_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkpoint_id", name="uq_risk_checkpoint_id"),
        sa.UniqueConstraint("thread_id", "version", name="uq_risk_checkpoint_thread_version"),
    )
    op.create_index(
        "ix_risk_checkpoint_task_version",
        "risk_graph_checkpoint",
        ["task_id", "version"],
    )
    op.create_index(
        "ix_risk_checkpoint_thread_version",
        "risk_graph_checkpoint",
        ["thread_id", "version"],
    )


def downgrade() -> None:
    op.drop_table("risk_graph_checkpoint")
    op.drop_table("risk_review_event")
    op.drop_table("risk_assessment_document")
    op.drop_table("risk_assessment_task")
    op.drop_column("file_parse_task", "original_filename")
