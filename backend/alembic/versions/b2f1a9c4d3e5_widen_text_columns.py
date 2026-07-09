"""Widen users.picture and summaries.sentiment to unbounded Text

Google profile-picture URLs and LLM-generated sentiment strings can exceed the
original varchar limits. Postgres enforces those limits (SQLite does not), so
the first real Google sign-in failed with StringDataRightTruncation. Text has
no length cap on Postgres.

Revision ID: b2f1a9c4d3e5
Revises: deccdfd3fb5f
Create Date: 2026-07-09

"""
from alembic import op
import sqlalchemy as sa

revision = "b2f1a9c4d3e5"
down_revision = "deccdfd3fb5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "picture",
            existing_type=sa.String(length=1000),
            type_=sa.Text(),
            existing_nullable=True,
        )
    with op.batch_alter_table("summaries") as batch_op:
        batch_op.alter_column(
            "sentiment",
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("summaries") as batch_op:
        batch_op.alter_column(
            "sentiment",
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "picture",
            existing_type=sa.Text(),
            type_=sa.String(length=1000),
            existing_nullable=True,
        )
