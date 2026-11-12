"""Add durable editorial requests pinned to a base report version."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b9c0d1e2f3a4"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("report_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")),
        sa.Column("result_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("report_versions.id", ondelete="SET NULL")),
        sa.Column("error_code", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "request_id", name="uq_report_revision_request"))
    for name in ("user_id", "research_task_id", "base_version_id", "workflow_run_id"):
        op.create_index(f"ix_report_revisions_{name}", "report_revisions", [name])
    op.create_index("uq_report_revision_active_task", "report_revisions", ["research_task_id"], unique=True,
                    postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"))


def downgrade():
    op.drop_table("report_revisions")
