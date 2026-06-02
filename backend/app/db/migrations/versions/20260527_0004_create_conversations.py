"""create conversations

Revision ID: 0004_create_conversations
Revises: 0003_create_auth_session
Create Date: 2026-05-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_create_conversations"
down_revision = "0003_create_auth_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("agent_code", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_conversation_id", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_agent_user", "conversation", ["agent_id", "user_id"])
    op.create_index(
        "ix_conversation_user_last_message",
        "conversation",
        ["user_id", "last_message_at"],
    )
    op.create_index(
        "ix_conversation_user_status_last_message",
        "conversation",
        ["user_id", "status", "last_message_at"],
    )

    op.create_table(
        "conversation_message",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("thought", sa.Text(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("invocation_record_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"]),
        sa.ForeignKeyConstraint(["invocation_record_id"], ["agent_invocation_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_message_conversation_created",
        "conversation_message",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_message_conversation_sequence",
        "conversation_message",
        ["conversation_id", "sequence_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_message_conversation_sequence", table_name="conversation_message")
    op.drop_index("ix_conversation_message_conversation_created", table_name="conversation_message")
    op.drop_table("conversation_message")
    op.drop_index("ix_conversation_user_status_last_message", table_name="conversation")
    op.drop_index("ix_conversation_user_last_message", table_name="conversation")
    op.drop_index("ix_conversation_agent_user", table_name="conversation")
    op.drop_table("conversation")
