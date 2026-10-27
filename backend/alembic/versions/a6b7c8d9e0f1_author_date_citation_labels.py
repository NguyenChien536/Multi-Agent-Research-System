"""Allow author-date citation labels without truncating source identity."""
from alembic import op
import sqlalchemy as sa

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("citations", "citation_label", existing_type=sa.String(20), type_=sa.String(500), existing_nullable=False)


def downgrade():
    # A lossy downgrade should require an explicit operator decision.
    op.alter_column("citations", "citation_label", existing_type=sa.String(500), type_=sa.String(20),
                    postgresql_using="left(citation_label, 20)", existing_nullable=False)
