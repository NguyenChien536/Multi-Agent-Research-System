"""Add bibliographic metadata and search provenance to research sources.

Revision ID: c4a71b10d001
Revises: b9c0d1e2f3a4
"""
from alembic import op
import sqlalchemy as sa


revision = "c4a71b10d001"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("research_sources", sa.Column("doi", sa.String(length=255), nullable=True))
    op.add_column("research_sources", sa.Column("venue", sa.String(length=500), nullable=True))
    op.add_column("research_sources", sa.Column("search_provider", sa.String(length=50), nullable=True))
    op.add_column("research_sources", sa.Column("full_text_url", sa.Text(), nullable=True))
    op.add_column("research_sources", sa.Column("text_scope", sa.String(length=20), nullable=True))
    op.create_index("ix_research_sources_doi", "research_sources", ["doi"], unique=False)


def downgrade():
    op.drop_index("ix_research_sources_doi", table_name="research_sources")
    op.drop_column("research_sources", "text_scope")
    op.drop_column("research_sources", "full_text_url")
    op.drop_column("research_sources", "search_provider")
    op.drop_column("research_sources", "venue")
    op.drop_column("research_sources", "doi")
