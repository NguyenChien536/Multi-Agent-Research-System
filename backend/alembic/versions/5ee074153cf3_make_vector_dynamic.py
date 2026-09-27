"""Make vector dynamic

Revision ID: 5ee074153cf3
Revises: d530fd23930b
Create Date: 2026-09-25 18:46:57.472285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ee074153cf3'
down_revision: Union[str, Sequence[str], None] = 'd530fd23930b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536)')
