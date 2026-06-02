"""create leads

Revision ID: 0005_create_leads
Revises: 0004_create_conversations
Create Date: 2026-06-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_create_leads"
down_revision = "0004_create_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_contact",
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("customer_name", sa.String(length=100), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("contact_type", sa.String(length=50), nullable=True),
        sa.Column("contact_value", sa.String(length=255), nullable=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_normalized", name="uq_lead_contact_phone_normalized"),
    )
    op.create_index("ix_lead_contact_org", "lead_contact", ["org_unit_id"])
    op.create_index("ix_lead_contact_user", "lead_contact", ["user_id"])

    op.create_table(
        "sales_lead",
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("agent_code", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("requirement_summary", sa.Text(), nullable=True),
        sa.Column("requirement_types", sa.JSON(), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["lead_contact.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_lead_contact", "sales_lead", ["contact_id"])
    op.create_index("ix_sales_lead_conversation", "sales_lead", ["conversation_id"])
    op.create_index("ix_sales_lead_user_agent_status", "sales_lead", ["user_id", "agent_id", "status"])

    op.create_table(
        "lead_capture_event",
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_message_id", sa.String(length=36), nullable=True),
        sa.Column("invocation_record_id", sa.String(length=36), nullable=True),
        sa.Column("sales_lead_id", sa.String(length=36), nullable=True),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("agent_code", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("raw_delta", sa.JSON(), nullable=False),
        sa.Column("normalized_delta", sa.JSON(), nullable=False),
        sa.Column("followup_decision", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["lead_contact.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"]),
        sa.ForeignKeyConstraint(["conversation_message_id"], ["conversation_message.id"]),
        sa.ForeignKeyConstraint(["invocation_record_id"], ["agent_invocation_record.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["sales_lead_id"], ["sales_lead.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_capture_event_conversation", "lead_capture_event", ["conversation_id"])
    op.create_index("ix_lead_capture_event_invocation", "lead_capture_event", ["invocation_record_id"])
    op.create_index("ix_lead_capture_event_lead", "lead_capture_event", ["sales_lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_capture_event_lead", table_name="lead_capture_event")
    op.drop_index("ix_lead_capture_event_invocation", table_name="lead_capture_event")
    op.drop_index("ix_lead_capture_event_conversation", table_name="lead_capture_event")
    op.drop_table("lead_capture_event")
    op.drop_index("ix_sales_lead_user_agent_status", table_name="sales_lead")
    op.drop_index("ix_sales_lead_conversation", table_name="sales_lead")
    op.drop_index("ix_sales_lead_contact", table_name="sales_lead")
    op.drop_table("sales_lead")
    op.drop_index("ix_lead_contact_user", table_name="lead_contact")
    op.drop_index("ix_lead_contact_org", table_name="lead_contact")
    op.drop_table("lead_contact")
