"""simplify embed session for industrial token exchange

Revision ID: 0007_simplify_embed_session
Revises: 0006_create_embed_session
Create Date: 2026-06-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_simplify_embed_session"
down_revision = "0006_create_embed_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("embed_session", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE embed_session SET expires_at = refresh_expires_at")
    op.alter_column("embed_session", "expires_at", nullable=False)

    op.drop_index("ix_embed_session_external_session", table_name="embed_session")
    op.execute("ALTER TABLE embed_session DROP CONSTRAINT IF EXISTS embed_session_org_unit_id_fkey")
    op.drop_column("embed_session", "external_session_id")
    op.drop_column("embed_session", "org_unit_id")
    op.drop_column("embed_session", "access_expires_at")
    op.drop_column("embed_session", "refresh_expires_at")
    op.drop_column("embed_session", "last_seen_at")
    op.drop_column("embed_session", "revoke_reason")
    op.drop_column("embed_session", "updated_at")

    op.execute(
        """
        UPDATE embed_session
        SET status = 'REVOKED',
            revoked_at = COALESCE(revoked_at, now())
        WHERE status = 'ACTIVE'
          AND id NOT IN (
            SELECT DISTINCT ON (external_user_id) id
            FROM embed_session
            WHERE status = 'ACTIVE'
            ORDER BY external_user_id, created_at DESC
          )
        """
    )

    op.create_index("ix_embed_session_agent_code", "embed_session", ["agent_code"])
    op.create_index("ix_embed_session_expires_at", "embed_session", ["expires_at"])
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_embed_session_active_external_user
        ON embed_session (external_user_id)
        WHERE status = 'ACTIVE'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_embed_session_active_external_user")
    op.drop_index("ix_embed_session_expires_at", table_name="embed_session")
    op.drop_index("ix_embed_session_agent_code", table_name="embed_session")

    op.add_column("embed_session", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("embed_session", sa.Column("revoke_reason", sa.String(length=100), nullable=True))
    op.add_column("embed_session", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("embed_session", sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("embed_session", sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("embed_session", sa.Column("org_unit_id", sa.String(length=36), nullable=True))
    op.add_column("embed_session", sa.Column("external_session_id", sa.String(length=100), nullable=True))

    op.execute(
        """
        UPDATE embed_session
        SET updated_at = created_at,
            last_seen_at = created_at,
            access_expires_at = expires_at,
            refresh_expires_at = expires_at
        """
    )
    op.alter_column("embed_session", "updated_at", nullable=False)
    op.alter_column("embed_session", "last_seen_at", nullable=False)
    op.alter_column("embed_session", "access_expires_at", nullable=False)
    op.alter_column("embed_session", "refresh_expires_at", nullable=False)

    op.create_foreign_key(
        "fk_embed_session_org_unit_id_org_unit",
        "embed_session",
        "org_unit",
        ["org_unit_id"],
        ["id"],
    )
    op.create_index("ix_embed_session_external_session", "embed_session", ["external_session_id"])
    op.drop_column("embed_session", "expires_at")
