"""Add ClaimEvidence junction table and Citation.chunk_id FK

Revision ID: a1b2c3d4e5f6
Revises: 5ee074153cf3
Create Date: 2026-10-01 00:10:00.000000

Changes:
- Add table: claim_evidences (claim_id PK/FK, evidence_id PK/FK, relevance_score)
- Remove column: research_claims.evidence_ids (UUID[] array — tech debt)
- Add column: citations.chunk_id (FK → document_chunks, nullable)
- Add column: citations.research_task_id (FK → research_tasks, for cross-entity constraint)
- Add column: citations.citation_number (int, replaces citation_label ordering)
- Add columns: research_sources.attribution, provider_name, license_name, source_page_url (for ADR-001 image support)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# revision identifiers
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5ee074153cf3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Add image/attribution columns to research_sources                 #
    # ------------------------------------------------------------------ #
    op.add_column(
        "research_sources",
        sa.Column("attribution", sa.String(500), nullable=True),
    )
    op.add_column(
        "research_sources",
        sa.Column("provider_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "research_sources",
        sa.Column("license_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "research_sources",
        sa.Column("source_page_url", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------ #
    # 2. Create claim_evidences junction table                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "claim_evidences",
        sa.Column(
            "claim_id",
            UUID(as_uuid=True),
            sa.ForeignKey("research_claims.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evidences.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "relevance_score",
            sa.Float(),
            nullable=True,
            comment="Optional relevance score assigned by Analyst agent (0.0–1.0)",
        ),
    )
    op.create_index(
        "ix_claim_evidences_evidence_id",
        "claim_evidences",
        ["evidence_id"],
    )

    # ------------------------------------------------------------------ #
    # 3. Data migration: expand evidence_ids array → junction rows        #
    # NOTE: This operates on a development DB with no production data.    #
    # For a DB with existing data, run a separate data migration script.  #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        INSERT INTO claim_evidences (claim_id, evidence_id)
        SELECT rc.id AS claim_id, refs.evidence_id
        FROM research_claims rc
        CROSS JOIN LATERAL unnest(rc.evidence_ids) AS refs(evidence_id)
        JOIN evidences e ON e.id = refs.evidence_id
        ON CONFLICT DO NOTHING;
        """
    )

    # ------------------------------------------------------------------ #
    # 4. Drop evidence_ids column from research_claims                    #
    # ------------------------------------------------------------------ #
    op.drop_column("research_claims", "evidence_ids")

    # ------------------------------------------------------------------ #
    # 5. Add task lineage to citations (validated against related entities) #
    # ------------------------------------------------------------------ #
    op.add_column(
        "citations",
        sa.Column(
            "research_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("research_tasks.id", ondelete="CASCADE"),
            nullable=True,  # nullable first; populate then tighten
        ),
    )
    op.create_index(
        "ix_citations_research_task_id",
        "citations",
        ["research_task_id"],
    )
    # Backfill from report's task
    op.execute(
        """
        UPDATE citations c
        SET research_task_id = rr.research_task_id
        FROM research_reports rr
        WHERE c.report_id = rr.id
          AND c.research_task_id IS NULL;
        """
    )
    # Existing citations must have a report, so the backfill should populate
    # every row before the task lineage is made mandatory.
    op.alter_column(
        "citations",
        "research_task_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # 6. Add chunk_id FK to citations (replaces chunk_reference string)  #
    # ------------------------------------------------------------------ #
    op.add_column(
        "citations",
        sa.Column(
            "chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to the specific DocumentChunk this citation references",
        ),
    )
    op.create_index(
        "ix_citations_chunk_id",
        "citations",
        ["chunk_id"],
    )
    # chunk_reference string stays for now as fallback; will be dropped after
    # chunk_id is populated by application layer. See migration guide below.

    # ------------------------------------------------------------------ #
    # 7. Add citation_number column (replaces citation_label for ordering)#
    # ------------------------------------------------------------------ #
    op.add_column(
        "citations",
        sa.Column(
            "citation_number",
            sa.Integer(),
            nullable=True,
            comment="Sequential citation number within a report, e.g. 1, 2, 3",
        ),
    )
    # Backfill citation_number from citation_label where possible
    op.execute(
        """
        UPDATE citations
        SET citation_number = NULLIF(regexp_replace(citation_label, '[^0-9]', '', 'g'), '')::int
        WHERE citation_label IS NOT NULL;
        """
    )


def downgrade() -> None:
    # Reverse in opposite order

    # 7. Remove citation_number
    op.drop_column("citations", "citation_number")

    # 6. Remove chunk_id from citations
    op.drop_index("ix_citations_chunk_id", table_name="citations")
    op.drop_column("citations", "chunk_id")

    # 5. Remove research_task_id from citations
    op.drop_index("ix_citations_research_task_id", table_name="citations")
    op.drop_column("citations", "research_task_id")

    # 4. Restore evidence_ids column on research_claims
    op.add_column(
        "research_claims",
        sa.Column(
            "evidence_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
    )
    # Reverse data migration: collapse junction rows back into array
    op.execute(
        """
        UPDATE research_claims rc
        SET evidence_ids = subq.ids
        FROM (
            SELECT claim_id, array_agg(evidence_id) AS ids
            FROM claim_evidences
            GROUP BY claim_id
        ) AS subq
        WHERE rc.id = subq.claim_id;
        """
    )

    # 3. Drop junction table
    op.drop_index("ix_claim_evidences_evidence_id", table_name="claim_evidences")
    op.drop_table("claim_evidences")

    # 2. Remove image/attribution columns from research_sources
    op.drop_column("research_sources", "source_page_url")
    op.drop_column("research_sources", "license_name")
    op.drop_column("research_sources", "provider_name")
    op.drop_column("research_sources", "attribution")
