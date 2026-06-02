"""create auth session

Revision ID: 0003_create_auth_session
Revises: 0002_add_user_login_credentials
Create Date: 2026-05-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_create_auth_session"
down_revision = "0002_add_user_login_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_session",
        sa.Column("session_hash", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("phone_normalized", sa.String(length=32), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=128), nullable=True),
        sa.Column("client_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_hash"),
    )
    op.create_index("ix_auth_session_idle_expires", "auth_session", ["idle_expires_at"])
    op.create_index("ix_auth_session_revoked", "auth_session", ["revoked_at"])
    op.create_index("ix_auth_session_user", "auth_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_session_user", table_name="auth_session")
    op.drop_index("ix_auth_session_revoked", table_name="auth_session")
    op.drop_index("ix_auth_session_idle_expires", table_name="auth_session")
    op.drop_table("auth_session")
