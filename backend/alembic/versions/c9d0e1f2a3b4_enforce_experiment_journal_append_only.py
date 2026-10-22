"""Enforce append-only experiment journal entries.

Revision ID: c9d0e1f2a3b4
Revises: a2b3c4d5e6f7
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION reject_experiment_journal_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'experiment_journal_entries is append-only'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER experiment_journal_append_only
        BEFORE UPDATE OR DELETE ON experiment_journal_entries
        FOR EACH ROW EXECUTE FUNCTION reject_experiment_journal_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS experiment_journal_append_only ON experiment_journal_entries")
    op.execute("DROP FUNCTION IF EXISTS reject_experiment_journal_mutation()")
