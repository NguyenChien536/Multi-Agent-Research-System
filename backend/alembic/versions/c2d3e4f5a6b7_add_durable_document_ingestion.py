"""Add durable PDF ingestion lifecycle and outbox.

Revision ID: c2d3e4f5a6b7
Revises: b8c9d0e1f2a3
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c2d3e4f5a6b7"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_sources",
        sa.Column("ingestion_status", sa.String(length=20), nullable=False, server_default="READY"),
    )
    op.add_column("research_sources", sa.Column("ingestion_error", sa.Text(), nullable=True))
    op.add_column(
        "research_sources",
        sa.Column("ingestion_attempt", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("research_sources", sa.Column("ingestion_lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "research_sources",
        sa.Column("upload_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("research_sources", sa.Column("content_checksum", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_research_sources_upload_artifact",
        "research_sources",
        "export_artifacts",
        ["upload_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_research_sources_ingestion_status", "research_sources", ["ingestion_status"])

    op.create_table(
        "document_ingestion_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unclaimed_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["research_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_document_ingestion_source"),
    )
    op.create_index("ix_document_ingestion_outbox_research_task_id", "document_ingestion_outbox", ["research_task_id"])
    op.create_index("ix_document_ingestion_outbox_source_id", "document_ingestion_outbox", ["source_id"])
    op.create_index("ix_document_ingestion_outbox_available_at", "document_ingestion_outbox", ["available_at"])
    op.create_index("ix_document_ingestion_outbox_dispatched_at", "document_ingestion_outbox", ["dispatched_at"])


def downgrade() -> None:
    op.drop_index("ix_document_ingestion_outbox_dispatched_at", table_name="document_ingestion_outbox")
    op.drop_index("ix_document_ingestion_outbox_available_at", table_name="document_ingestion_outbox")
    op.drop_index("ix_document_ingestion_outbox_source_id", table_name="document_ingestion_outbox")
    op.drop_index("ix_document_ingestion_outbox_research_task_id", table_name="document_ingestion_outbox")
    op.drop_table("document_ingestion_outbox")
    op.drop_index("ix_research_sources_ingestion_status", table_name="research_sources")
    op.drop_constraint("fk_research_sources_upload_artifact", "research_sources", type_="foreignkey")
    op.drop_column("research_sources", "content_checksum")
    op.drop_column("research_sources", "upload_artifact_id")
    op.drop_column("research_sources", "ingestion_lease_until")
    op.drop_column("research_sources", "ingestion_attempt")
    op.drop_column("research_sources", "ingestion_error")
    op.drop_column("research_sources", "ingestion_status")
