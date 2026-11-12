"""Persist owner-scoped, version-pinned report questions.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("report_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("references", postgresql.JSONB(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=True),
        sa.Column("context_truncated", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "request_id", name="uq_report_question_request"),
    )
    op.create_index("uq_report_question_active_user", "report_questions", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'RUNNING'"))
    op.create_index("ix_report_questions_version_created", "report_questions", ["report_version_id", "created_at", "id"])


def downgrade():
    op.drop_table("report_questions")
