"""Add durable task dispatch outbox.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("research_tasks", sa.Column("worker_lease_until", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "task_dispatch_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "research_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("research_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=40), nullable=False, server_default="START_RESEARCH"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("research_task_id", "event_type", name="uq_task_dispatch_event"),
    )
    op.create_index("ix_task_dispatch_outbox_research_task_id", "task_dispatch_outbox", ["research_task_id"])
    op.create_index("ix_task_dispatch_outbox_available_at", "task_dispatch_outbox", ["available_at"])
    op.create_index("ix_task_dispatch_outbox_dispatched_at", "task_dispatch_outbox", ["dispatched_at"])


def downgrade() -> None:
    op.drop_index("ix_task_dispatch_outbox_dispatched_at", table_name="task_dispatch_outbox")
    op.drop_index("ix_task_dispatch_outbox_available_at", table_name="task_dispatch_outbox")
    op.drop_index("ix_task_dispatch_outbox_research_task_id", table_name="task_dispatch_outbox")
    op.drop_table("task_dispatch_outbox")
    op.drop_column("research_tasks", "worker_lease_until")
