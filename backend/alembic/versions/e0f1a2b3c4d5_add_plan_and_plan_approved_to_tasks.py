"""Add plan and plan_approved to research_tasks.

Revision ID: e0f1a2b3c4d5
Revises: c8d9e0f1a2b3
Create Date: 2026-10-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("research_tasks", sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("research_tasks", sa.Column("plan_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("research_tasks", sa.Column("plan_feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("research_tasks", "plan_feedback")
    op.drop_column("research_tasks", "plan_approved")
    op.drop_column("research_tasks", "plan")
