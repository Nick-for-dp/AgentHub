"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_unit",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_account",
        sa.Column("org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("user_type", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_account_email", "user_account", ["email"])
    op.create_index("ix_user_account_phone_normalized", "user_account", ["phone_normalized"])
    op.create_index(
        "uq_user_account_external_phone",
        "user_account",
        ["phone_normalized"],
        unique=True,
        postgresql_where=sa.text("user_type = 'EXTERNAL_CUSTOMER' AND phone_normalized IS NOT NULL"),
    )

    op.create_table(
        "api_key",
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("issued_for_phone", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_key_issued_for_phone", "api_key", ["issued_for_phone"])
    op.create_index("ix_api_key_key_prefix", "api_key", ["key_prefix"])
    op.create_index("ix_api_key_owner", "api_key", ["owner_type", "owner_id"])

    op.create_table(
        "permission_policy",
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permission_resource", "permission_policy", ["resource_type", "resource_id"])
    op.create_index("ix_permission_subject", "permission_policy", ["subject_type", "subject_id"])

    op.create_table(
        "agent",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_type", sa.String(length=50), nullable=False),
        sa.Column("runtime_app_id", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("publish_status", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_agent_code"),
    )
    op.create_index("ix_agent_owner", "agent", ["owner_org_unit_id"])

    op.create_table(
        "knowledge_base",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_kb_id", sa.String(length=200), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("retrieval_config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_base_owner", "knowledge_base", ["owner_org_unit_id"])
    op.create_index("ix_knowledge_base_provider_kb", "knowledge_base", ["provider", "provider_kb_id"])

    op.create_table(
        "agent_knowledge_base",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "knowledge_base_id", name="uq_agent_knowledge_base"),
    )
    op.create_index("ix_agent_kb_agent", "agent_knowledge_base", ["agent_id"])
    op.create_index("ix_agent_kb_kb", "agent_knowledge_base", ["knowledge_base_id"])

    op.create_table(
        "document",
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("owner_org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_uri", sa.String(length=500), nullable=True),
        sa.Column("provider_doc_id", sa.String(length=200), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("chunk_version", sa.String(length=100), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"]),
        sa.ForeignKeyConstraint(["owner_org_unit_id"], ["org_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_kb", "document", ["knowledge_base_id"])
    op.create_index("ix_document_provider_doc", "document", ["provider_doc_id"])

    op.create_table(
        "document_chunk",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("vector_id", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )
    op.create_index("ix_document_chunk_kb", "document_chunk", ["knowledge_base_id"])

    op.create_table(
        "agent_invocation_record",
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=True),
        sa.Column("caller_type", sa.String(length=32), nullable=False),
        sa.Column("source_channel", sa.String(length=50), nullable=True),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("stream_mode", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retrieval_snapshot", sa.JSON(), nullable=False),
        sa.Column("model_snapshot", sa.JSON(), nullable=False),
        sa.Column("runtime_snapshot", sa.JSON(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("feedback_score", sa.Integer(), nullable=True),
        sa.Column("evaluation_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_key.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["agent_invocation_record.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invocation_agent_created", "agent_invocation_record", ["agent_id", "created_at"])
    op.create_index("ix_invocation_api_key_created", "agent_invocation_record", ["api_key_id", "created_at"])
    op.create_index("ix_invocation_org_created", "agent_invocation_record", ["org_unit_id", "created_at"])
    op.create_index("ix_invocation_request_id", "agent_invocation_record", ["request_id"])

    op.create_table(
        "evaluation_case",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("case_type", sa.String(length=50), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=False),
        sa.Column("reference_context", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_case_agent", "evaluation_case", ["agent_id"])

    op.create_table(
        "evaluation_result",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_case_id", sa.String(length=36), nullable=True),
        sa.Column("invocation_record_id", sa.String(length=36), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("judge_type", sa.String(length=50), nullable=False),
        sa.Column("judge_model", sa.String(length=100), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["evaluation_case_id"], ["evaluation_case.id"]),
        sa.ForeignKeyConstraint(["invocation_record_id"], ["agent_invocation_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_result_agent", "evaluation_result", ["agent_id"])
    op.create_index("ix_evaluation_result_case", "evaluation_result", ["evaluation_case_id"])
    op.create_index("ix_evaluation_result_invocation", "evaluation_result", ["invocation_record_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_result_invocation", table_name="evaluation_result")
    op.drop_index("ix_evaluation_result_case", table_name="evaluation_result")
    op.drop_index("ix_evaluation_result_agent", table_name="evaluation_result")
    op.drop_table("evaluation_result")
    op.drop_index("ix_evaluation_case_agent", table_name="evaluation_case")
    op.drop_table("evaluation_case")
    op.drop_index("ix_invocation_request_id", table_name="agent_invocation_record")
    op.drop_index("ix_invocation_org_created", table_name="agent_invocation_record")
    op.drop_index("ix_invocation_api_key_created", table_name="agent_invocation_record")
    op.drop_index("ix_invocation_agent_created", table_name="agent_invocation_record")
    op.drop_table("agent_invocation_record")
    op.drop_index("ix_document_chunk_kb", table_name="document_chunk")
    op.drop_table("document_chunk")
    op.drop_index("ix_document_provider_doc", table_name="document")
    op.drop_index("ix_document_kb", table_name="document")
    op.drop_table("document")
    op.drop_index("ix_agent_kb_kb", table_name="agent_knowledge_base")
    op.drop_index("ix_agent_kb_agent", table_name="agent_knowledge_base")
    op.drop_table("agent_knowledge_base")
    op.drop_index("ix_knowledge_base_provider_kb", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_owner", table_name="knowledge_base")
    op.drop_table("knowledge_base")
    op.drop_index("ix_agent_owner", table_name="agent")
    op.drop_table("agent")
    op.drop_index("ix_permission_subject", table_name="permission_policy")
    op.drop_index("ix_permission_resource", table_name="permission_policy")
    op.drop_table("permission_policy")
    op.drop_index("ix_api_key_owner", table_name="api_key")
    op.drop_index("ix_api_key_key_prefix", table_name="api_key")
    op.drop_index("ix_api_key_issued_for_phone", table_name="api_key")
    op.drop_table("api_key")
    op.drop_index("uq_user_account_external_phone", table_name="user_account")
    op.drop_index("ix_user_account_phone_normalized", table_name="user_account")
    op.drop_index("ix_user_account_email", table_name="user_account")
    op.drop_table("user_account")
    op.drop_table("org_unit")
