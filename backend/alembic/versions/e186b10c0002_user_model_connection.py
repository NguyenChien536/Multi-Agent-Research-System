"""Persist an encrypted, owner-bound default model connection."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'e186b10c0002'
down_revision = 'd075b10c0001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('model_connection', JSONB(), nullable=True))

def downgrade():
    op.drop_column('users', 'model_connection')
