"""create embed session

Revision ID: 0006_create_embed_session
Revises: 0005_create_leads
Create Date: 2026-06-11 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_create_embed_session"
down_revision = "0005_create_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embed_session",
        sa.Column("session_hash", sa.String(length=128), nullable=False),
        sa.Column("external_user_id", sa.String(length=100), nullable=False),
        sa.Column("external_session_id", sa.String(length=100), nullable=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("agent_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=100), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_hash"),
    )
    op.create_index("ix_embed_session_external_session", "embed_session", ["external_session_id"])
    op.create_index("ix_embed_session_external_user", "embed_session", ["external_user_id"])
    op.create_index("ix_embed_session_hash", "embed_session", ["session_hash"])
    op.create_index("ix_embed_session_status", "embed_session", ["status"])
    op.create_index("ix_embed_session_user", "embed_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_embed_session_user", table_name="embed_session")
    op.drop_index("ix_embed_session_status", table_name="embed_session")
    op.drop_index("ix_embed_session_hash", table_name="embed_session")
    op.drop_index("ix_embed_session_external_user", table_name="embed_session")
    op.drop_index("ix_embed_session_external_session", table_name="embed_session")
    op.drop_table("embed_session")
