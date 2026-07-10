"""add tasks table

Revision ID: c4e9a1b7d820
Revises: 3a732e1e88cc
Create Date: 2026-07-10 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e9a1b7d820'
down_revision = '3a732e1e88cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('workspace_id', sa.String(length=32), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=True),
        sa.Column('meeting_id', sa.String(length=32), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('owner', sa.String(length=200), nullable=True),
        sa.Column('due', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='todo'),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('done_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_workspace_id'), 'tasks', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_tasks_meeting_id'), 'tasks', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_meeting_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_workspace_id'), table_name='tasks')
    op.drop_table('tasks')
