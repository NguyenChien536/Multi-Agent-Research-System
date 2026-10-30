"""Bounded passage-level evidence review. Judgments are internal LLM assessments."""
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceReview(BaseModel):
    statement_id: str
    judgment: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "CONTRADICTED", "UNVERIFIABLE"]
    reason: str = Field(min_length=1, max_length=1000)


def prepare_evidence_review(section_text: str, claims: list[dict], *, central_headings: list[str],
                            draft: str, max_units: int = 16, max_evidence: int = 24) -> dict:
    """Select cited evidence by identity, never by its position in a global list."""
    records = {str(c.get("claim_id")): c for c in claims if c.get("claim_id")}
    marker = r"\[\[@claim:([^\]]+)\]\]"
    draft_refs = list(dict.fromkeys(re.findall(marker, draft)))
    units, requested, findings = [], [], []
    heading = ""
    for index, paragraph in enumerate(section_text.split("\n\n")):
        lines = paragraph.splitlines()
        if lines and lines[0].startswith("## "):
            heading = lines[0][3:].strip()
            paragraph = "\n".join(lines[1:]).strip()
        refs = list(dict.fromkeys(re.findall(marker, paragraph)))
        if not paragraph or (not refs and heading not in central_headings):
            continue
        if paragraph.startswith(("|", "![", "[[figure:")):
            continue
        identity = hashlib.sha256(f"{index}:{heading}:{paragraph}".encode()).hexdigest()[:20]
        context_refs = refs or draft_refs
        requested.extend(context_refs)
        if len(paragraph) > 4000:
            findings.append(f"Passage {identity} exceeds the evidence-review text limit.")
        units.append({"statement_id": identity, "section": heading,
                      "passage": paragraph[:4000], "claim_ids": context_refs,
                      "kind": "cited_passage" if refs else "interpretation"})
    if len(units) > max_units:
        findings.append("This batch exceeds the passage-review limit; unreviewed passages require review.")
    requested = list(dict.fromkeys(requested))
    if len(requested) > max_evidence:
        findings.append("This batch exceeds the evidence-context limit; do not infer complete support.")
    evidence = []
    for claim_id in requested[:max_evidence]:
        item = records.get(claim_id)
        if not item or not all(item.get(k) for k in ("evidence_id", "source_id", "chunk_id")):
            findings.append(f"Claim {claim_id} has no complete evidence lineage.")
            continue
        claim = str(item.get("claim") or item.get("claim_text") or "")
        quote = str(item.get("evidence_quote") or item.get("evidence_text") or "")
        if not quote.strip():
            findings.append(f"Claim {claim_id} has no evidence quote available for review.")
        if len(claim) > 2000 or len(quote) > 3000:
            findings.append(f"Evidence for {claim_id} exceeds the context limit.")
        evidence.append({"claim_id": claim_id, "claim": claim[:2000], "quote": quote[:3000],
                         **{k: item.get(k) for k in ("source_id", "chunk_id", "source_title", "text_scope", "doi")}})
    return {"units": units[:max_units], "evidence": evidence, "coverage_findings": findings}


def evaluate_evidence_reviews(prepared: dict, reviews: list[EvidenceReview]) -> dict:
    expected = {unit["statement_id"] for unit in prepared["units"]}
    findings = list(prepared["coverage_findings"])
    seen, accepted = set(), []
    for review in reviews:
        if review.statement_id not in expected or review.statement_id in seen:
            findings.append("The reviewer returned an unknown or duplicate passage identity.")
            continue
        seen.add(review.statement_id)
        accepted.append(review.model_dump())
    if expected - seen:
        findings.append(f"Missing support judgments for {len(expected - seen)} passages.")
    return {"expected_passages": len(expected), "reviewed_passages": len(seen),
            "coverage_complete": not findings, "findings": findings, "judgments": accepted,
            "all_supported": not findings and all(r["judgment"] == "SUPPORTED" for r in accepted)}


def audit_matches_draft(metadata: dict, draft: str) -> bool:
    audit = metadata.get("evidence_support_review") or {}
    return bool(audit.get("coverage_complete") and audit.get("all_supported")
                and audit.get("draft_sha256") == hashlib.sha256(draft.encode()).hexdigest())
