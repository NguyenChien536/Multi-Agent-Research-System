"""Persist query coverage for collected sources."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d075b10c0001"
down_revision = "c4a71b10d001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("research_sources", sa.Column("discovery_queries", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade():
    op.drop_column("research_sources", "discovery_queries")
