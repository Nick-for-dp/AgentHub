"""add user login credentials

Revision ID: 0002_add_user_login_credentials
Revises: 0001_initial_schema
Create Date: 2026-05-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_user_login_credentials"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_account",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_account",
        sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_account",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_account", "token_version")
    op.drop_column("user_account", "password_updated_at")
    op.drop_column("user_account", "password_hash")
