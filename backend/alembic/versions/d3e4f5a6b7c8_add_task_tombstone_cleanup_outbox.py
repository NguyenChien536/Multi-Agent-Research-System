"""Add task tombstones and durable cleanup outbox.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_tasks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "task_deletion_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_task_id", name="uq_task_deletion_research_task"),
    )
    op.create_index("ix_task_deletion_outbox_available_at", "task_deletion_outbox", ["available_at"])
    op.create_index("ix_task_deletion_outbox_dispatched_at", "task_deletion_outbox", ["dispatched_at"])


def downgrade() -> None:
    op.drop_index("ix_task_deletion_outbox_dispatched_at", table_name="task_deletion_outbox")
    op.drop_index("ix_task_deletion_outbox_available_at", table_name="task_deletion_outbox")
    op.drop_table("task_deletion_outbox")
    op.drop_column("research_tasks", "deleted_at")
