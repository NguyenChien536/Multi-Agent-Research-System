"""Store report content and citations in immutable version snapshots.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-26
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plan_version", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("review_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["research_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version_number", name="uq_report_version_number"),
        sa.UniqueConstraint("report_id", "workflow_run_id", name="uq_report_version_workflow_run"),
        sa.UniqueConstraint("id", "report_id", name="uq_report_version_id_report"),
    )
    op.create_index("ix_report_versions_report_id", "report_versions", ["report_id"])
    op.create_index("ix_report_versions_workflow_run_id", "report_versions", ["workflow_run_id"])

    # Backfill each legacy mutable report into its initial immutable snapshot.
    bind = op.get_bind()
    legacy_reports = bind.execute(sa.text(
        """SELECT r.id, r.title, r.content_markdown, r.executive_summary, r.review_status,
                  r.review_metadata, r.word_count, r.created_at, t.plan_version
           FROM research_reports AS r
           JOIN research_tasks AS t ON t.id = r.research_task_id"""
    )).mappings().all()
    version_ids: dict[uuid.UUID, uuid.UUID] = {}
    for report in legacy_reports:
        version_id = uuid.uuid4()
        version_ids[report["id"]] = version_id
        bind.execute(
            sa.text(
                """INSERT INTO report_versions
                   (id, report_id, version_number, workflow_run_id, plan_version,
                    title, content_markdown, executive_summary, review_status, review_metadata, word_count, created_at)
                   VALUES (:id, :report_id, 1, NULL, :plan_version,
                           :title, :content_markdown, :executive_summary, :review_status, :review_metadata, :word_count, :created_at)"""
            ).bindparams(sa.bindparam("review_metadata", type_=postgresql.JSONB())),
            {
                "id": version_id,
                "report_id": report["id"],
                "plan_version": report["plan_version"],
                "title": report["title"],
                "content_markdown": report["content_markdown"],
                "executive_summary": report["executive_summary"],
                "review_status": report["review_status"],
                "review_metadata": report["review_metadata"],
                "word_count": report["word_count"],
                "created_at": report["created_at"],
            },
        )

    op.add_column("citations", sa.Column("report_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    for report_id, version_id in version_ids.items():
        bind.execute(
            sa.text("UPDATE citations SET report_version_id = :version_id WHERE report_id = :report_id"),
            {"version_id": version_id, "report_id": report_id},
        )
    op.alter_column("citations", "report_version_id", nullable=False)
    op.create_index("ix_citations_report_version_id", "citations", ["report_version_id"])
    op.create_foreign_key(
        "fk_citations_report_version_id",
        "citations",
        "report_versions",
        ["report_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_citations_report_version_identity",
        "citations",
        "report_versions",
        ["report_version_id", "report_id"],
        ["id", "report_id"],
        ondelete="CASCADE",
    )

    # ResearchReport becomes an identity row; version snapshots are now the
    # only source of truth for report content and review metadata.
    op.drop_column("research_reports", "title")
    op.drop_column("research_reports", "content_markdown")
    op.drop_column("research_reports", "executive_summary")
    op.drop_column("research_reports", "review_status")
    op.drop_column("research_reports", "review_metadata")
    op.drop_column("research_reports", "word_count")
    op.drop_column("research_reports", "updated_at")


def downgrade() -> None:
    op.add_column("research_reports", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("research_reports", sa.Column("word_count", sa.Integer(), nullable=True))
    op.add_column("research_reports", sa.Column("review_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("research_reports", sa.Column("review_status", sa.String(length=30), nullable=True))
    op.add_column("research_reports", sa.Column("executive_summary", sa.Text(), nullable=True))
    op.add_column("research_reports", sa.Column("content_markdown", sa.Text(), nullable=True))
    op.add_column("research_reports", sa.Column("title", sa.String(length=255), nullable=True))

    bind = op.get_bind()
    versions = bind.execute(sa.text(
        """SELECT DISTINCT ON (report_id) report_id, title, content_markdown, executive_summary,
                  review_status, review_metadata, word_count, created_at
           FROM report_versions ORDER BY report_id, version_number DESC"""
    )).mappings().all()
    for version in versions:
        bind.execute(
            sa.text(
                """UPDATE research_reports
                   SET title=:title, content_markdown=:content_markdown, executive_summary=:executive_summary,
                       review_status=:review_status, review_metadata=:review_metadata,
                       word_count=:word_count, created_at=:created_at, updated_at=:created_at
                   WHERE id=:report_id"""
            ).bindparams(sa.bindparam("review_metadata", type_=postgresql.JSONB())),
            {
                "report_id": version["report_id"],
                "title": version["title"],
                "content_markdown": version["content_markdown"],
                "executive_summary": version["executive_summary"],
                "review_status": version["review_status"],
                "review_metadata": version["review_metadata"],
                "word_count": version["word_count"],
                "created_at": version["created_at"],
            },
        )
    op.alter_column("research_reports", "title", nullable=False)
    op.alter_column("research_reports", "content_markdown", nullable=False)
    op.alter_column("research_reports", "review_status", nullable=False, server_default="NEEDS_REVIEW")
    op.alter_column("research_reports", "review_metadata", nullable=False, server_default=sa.text("'{}'::jsonb"))
    op.alter_column("research_reports", "word_count", nullable=False, server_default="0")
    op.alter_column("research_reports", "updated_at", nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))

    op.drop_constraint("fk_citations_report_version_identity", "citations", type_="foreignkey")
    op.drop_constraint("fk_citations_report_version_id", "citations", type_="foreignkey")
    op.drop_index("ix_citations_report_version_id", table_name="citations")
    op.drop_column("citations", "report_version_id")
    op.drop_index("ix_report_versions_workflow_run_id", table_name="report_versions")
    op.drop_index("ix_report_versions_report_id", table_name="report_versions")
    op.drop_table("report_versions")
