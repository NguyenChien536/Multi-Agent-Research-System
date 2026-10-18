"""Add analysis_runs and experiment_journal_entries tables.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "research_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("routine_name", sa.String(length=100), server_default="tabular_regression_v1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="STARTED", nullable=False),
        sa.Column(
            "dataset_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("export_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_checksum", sa.String(length=64), nullable=True),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reproducibility_status", sa.String(length=30), server_default="NOT_RUN", nullable=False),
        sa.Column("reproducibility_diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "experiment_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "research_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "analysis_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("artifact_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", "sequence", name="uq_journal_run_sequence"),
    )


def downgrade() -> None:
    op.drop_table("experiment_journal_entries")
    op.drop_table("analysis_runs")
