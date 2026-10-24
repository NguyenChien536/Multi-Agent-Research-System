"""Merge durable workflow and report review migration heads.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2, e2f3a4b5c6d7
Create Date: 2026-10-24
"""
from typing import Sequence, Union


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = ("a7b8c9d0e1f2", "e2f3a4b5c6d7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
