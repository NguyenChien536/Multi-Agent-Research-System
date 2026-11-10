"""Persist account deletion intent until private task cleanup completes."""
from alembic import op
import sqlalchemy as sa

revision = 'f297c20d0003'
down_revision = 'e186b10c0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'deleted_at')
