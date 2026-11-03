"""Persistence and validation helpers for claim-to-source grounding."""

import uuid
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grounding import ClaimEvidence, Evidence, ResearchClaim
from app.models.source import DocumentChunk, ResearchSource


def _stable_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def source_quote_span(content: str, proposed: str) -> str | None:
    """Return original source text, permitting only whitespace alignment.

    PDF line wraps and HTML nonbreaking spaces can differ from the model's JSON
    string. Map that spelling back to a literal source span; never normalize
    case, punctuation, words or hyphens and never persist a reconstructed quote.
    """
    if not proposed.strip():
        return None
    if proposed in content:
        return proposed
    target = " ".join(proposed.split())
    if not target:
        return None
    normalized, positions = [], []
    for match in re.finditer(r"\s+|\S+", content):
        part = match.group()
        if part.isspace():
            normalized.append(" ")
            positions.append((match.start(), match.end()))
        else:
            normalized.extend(part)
            positions.extend((i, i+1) for i in range(match.start(), match.end()))
    start = "".join(normalized).find(target)
    if start < 0:
        return None
    return content[positions[start][0]:positions[start+len(target)-1][1]]


async def persist_grounded_claims(
    db: AsyncSession,
    task_id: uuid.UUID,
    extracted_claims: list[dict[str, Any]],
    retrieved_chunks: list[DocumentChunk],
) -> list[dict[str, Any]]:
    """Persist only claims whose non-empty quote occurs in a retrieved task chunk.

    Persisted quotes are always literal source substrings. Whitespace-only
    spelling differences can be mapped back to that original source span.
    """
    chunks_by_id = {chunk.id: chunk for chunk in retrieved_chunks}
    valid: list[dict[str, Any]] = []
    seen: set[tuple[str, uuid.UUID, str]] = set()

    for item in extracted_claims:
        claim_text = str(item.get("claim", "")).strip()
        quote = str(item.get("evidence_quote", "")).strip()
        if not claim_text or not _stable_key(quote):
            continue

        # Identical boilerplate can occur in several papers. Respect a supplied
        # chunk identity and reject ambiguous legacy extractions, rather than
        # silently attributing the quote to the first source in retrieval order.
        if item.get("chunk_id"):
            try:
                chunk = chunks_by_id.get(uuid.UUID(str(item["chunk_id"])))
            except (ValueError, TypeError, AttributeError):
                continue
            matched = source_quote_span(chunk.content, quote) if chunk is not None else None
            if matched is None:
                continue
        else:
            matches = [(candidate, source_quote_span(candidate.content, quote)) for candidate in chunks_by_id.values()]
            matches = [(candidate, span) for candidate, span in matches if span is not None]
            if len(matches) != 1:
                continue
            chunk, matched = matches[0]
        if chunk is None or chunk.research_task_id != task_id:
            continue
        match_method = "EXACT" if matched == quote else "WHITESPACE_ALIGNED_TO_SOURCE"
        quote = matched

        source = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.id == chunk.source_id,
                ResearchSource.research_task_id == task_id,
            )
        )
        if source is None:
            continue

        claim_key = (_stable_key(claim_text), chunk.id, quote)
        if claim_key in seen:
            continue
        seen.add(claim_key)

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
                confidence_score=1.0,  # Literal quote presence only, never a probability of truth.
            )
            db.add(evidence)
            await db.flush()

        # A copyable claim marker must identify one exact provenance record.
        # Reusing a text-only claim across papers aliases its marker and causes
        # downstream dictionaries to silently discard all but one source. Keep
        # historical many-to-many records intact; new markers are quote-scoped.
        other_proof = select(ClaimEvidence.claim_id).where(
            ClaimEvidence.claim_id == ResearchClaim.id,
            ClaimEvidence.evidence_id != evidence.id,
        ).correlate(ResearchClaim).exists()
        claim = await db.scalar(select(ResearchClaim).join(
            ClaimEvidence, ClaimEvidence.claim_id == ResearchClaim.id,
        ).where(ResearchClaim.research_task_id == task_id,
                ResearchClaim.claim_text == claim_text,
                ClaimEvidence.evidence_id == evidence.id, ~other_proof)
            .order_by(ResearchClaim.created_at, ResearchClaim.id).limit(1))
        if claim is None:
            claim = ResearchClaim(research_task_id=task_id, claim_text=claim_text, is_verified=False)
            db.add(claim)
            await db.flush()
        link = await db.get(ClaimEvidence, (claim.id, evidence.id))
        if link is None:
            db.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id))
        claim.is_verified = True
        claim.verification_note = "Verbatim quote matched its source chunk; semantic entailment and scientific validity remain unverified."

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
            "quote_match_method": match_method,
            "evidence_need_id": str(item.get("evidence_need_id") or "")[:40],
            "assumptions": [v.strip() for v in (item.get("assumptions") or [])[:8]
                            if isinstance(v, str) and v.strip() and len(v.strip()) <= 300 and v.strip() in chunk.content],
        })

    await db.flush()
    return valid
