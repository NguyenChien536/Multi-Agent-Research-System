"""Store private completed provider units for checkpoint retries.

Revision ID: g308d31e0004
Revises: f297c20d0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'g308d31e0004'
down_revision = 'f297c20d0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('provider_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('research_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('research_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation', sa.String(80), nullable=False),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workflow_run_id','operation','input_hash',name='uq_provider_result_unit'))
    op.create_index('ix_provider_results_research_task_id','provider_results',['research_task_id'])


def downgrade():
    op.drop_table('provider_results')
