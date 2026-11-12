"""Add research_type, protocol_artifact_id, and user_data_submission to research_tasks.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-10-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_tasks",
        sa.Column("research_type", sa.String(length=30), server_default="REVIEW", nullable=False),
    )
    op.add_column(
        "research_tasks",
        sa.Column(
            "protocol_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("export_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "research_tasks",
        sa.Column("user_data_submission", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_tasks", "user_data_submission")
    op.drop_column("research_tasks", "protocol_artifact_id")
    op.drop_column("research_tasks", "research_type")
