"""Persistence and validation helpers for claim-to-source grounding."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grounding import ClaimEvidence, Evidence, ResearchClaim
from app.models.source import DocumentChunk, ResearchSource


def _stable_key(value: str) -> str:
    return " ".join(value.split()).casefold()


async def persist_grounded_claims(
    db: AsyncSession,
    task_id: uuid.UUID,
    extracted_claims: list[dict[str, Any]],
    retrieved_chunks: list[DocumentChunk],
) -> list[dict[str, Any]]:
    """Persist only claims whose non-empty quote occurs in a retrieved task chunk.

    Quote validation is intentionally exact substring matching. Whitespace is
    normalized only to reject empty/whitespace-only values, never to make a
    quote pass when its original text is absent from the source chunk.
    """
    chunks_by_id = {chunk.id: chunk for chunk in retrieved_chunks}
    valid: list[dict[str, Any]] = []
    seen: set[tuple[str, uuid.UUID]] = set()

    for item in extracted_claims:
        claim_text = str(item.get("claim", "")).strip()
        quote = str(item.get("evidence_quote", "")).strip()
        if not claim_text or not _stable_key(quote):
            continue

        chunk = next(
            (
                candidate
                for candidate in chunks_by_id.values()
                if quote in candidate.content
            ),
            None,
        )
        if chunk is None or chunk.research_task_id != task_id:
            continue

        source = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.id == chunk.source_id,
                ResearchSource.research_task_id == task_id,
            )
        )
        if source is None:
            continue

        claim_key = (_stable_key(claim_text), chunk.id)
        if claim_key in seen:
            continue
        seen.add(claim_key)

        claim = await db.scalar(
            select(ResearchClaim).where(
                ResearchClaim.research_task_id == task_id,
                ResearchClaim.claim_text == claim_text,
            )
        )
        if claim is None:
            claim = ResearchClaim(
                research_task_id=task_id,
                claim_text=claim_text,
                is_verified=False,
            )
            db.add(claim)
            await db.flush()

        evidence = await db.scalar(
            select(Evidence).where(
                Evidence.research_task_id == task_id,
                Evidence.chunk_id == chunk.id,
                Evidence.content == quote,
            )
        )
        if evidence is None:
            evidence = Evidence(
                research_task_id=task_id,
                source_id=source.id,
                chunk_id=chunk.id,
                content=quote,
                evidence_type="QUOTE",
                confidence_score=1.0,
            )
            db.add(evidence)
            await db.flush()

        link = await db.get(ClaimEvidence, (claim.id, evidence.id))
        if link is None:
            db.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id))
        claim.is_verified = True
        claim.verification_note = "Evidence quote matched the retrieved source chunk exactly."

        valid.append({
            "claim_id": str(claim.id),
            "claim": claim.claim_text,
            "evidence_id": str(evidence.id),
            "evidence_quote": evidence.content,
            "source_id": str(source.id),
            "source_tag": source.source_tag,
            "source_title": source.title,
            "source_url": source.url,
            "source_author": source.author,
            "publication_date": source.publication_date,
            "source_type": source.source_type,
            "doi": source.doi,
            "venue": source.venue,
            "search_provider": source.search_provider,
            "text_scope": source.text_scope,
            "discovery_queries": source.discovery_queries or [],
            "chunk_id": str(chunk.id),
        })

    await db.flush()
    return valid
