"""Add durable workflow run identities and versioned resume decisions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("research_tasks", sa.Column("plan_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("research_tasks", sa.Column("resume_action", sa.String(length=40), nullable=True))
    op.add_column("research_tasks", sa.Column("resume_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("research_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("plan_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="RUNNING", nullable=False),
        sa.Column("checkpoint_thread_id", sa.String(length=64), nullable=False),
        sa.Column("last_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("research_task_id", "run_number", name="uq_workflow_run_number"),
        sa.UniqueConstraint("checkpoint_thread_id", name="uq_workflow_runs_checkpoint_thread_id"),
    )
    op.create_index("ix_workflow_runs_research_task_id", "workflow_runs", ["research_task_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_research_task_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_column("research_tasks", "resume_payload")
    op.drop_column("research_tasks", "resume_action")
    op.drop_column("research_tasks", "plan_version")
