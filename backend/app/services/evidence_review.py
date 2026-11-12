"""Bounded passage-level evidence review. Judgments are internal LLM assessments."""
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field


class QuoteAnchor(BaseModel):
    """A reviewer must point back to a supplied quote, never generate new evidence."""
    claim_id: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=40)
    chunk_id: str = Field(min_length=1, max_length=40)
    quote: str = Field(min_length=1, max_length=400)


class EvidenceReview(BaseModel):
    statement_id: str
    judgment: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "CONTRADICTED", "UNVERIFIABLE"]
    reason: str = Field(min_length=1, max_length=1000)
    supporting_claim_ids: list[str] = Field(default_factory=list, max_length=24)
    quote_anchors: list[QuoteAnchor] = Field(default_factory=list, max_length=8)
    supporting_execution_fact_ids: list[str] = Field(default_factory=list, max_length=8)
    assumptions_preserved: bool = False


def prepare_evidence_review(section_text: str, claims: list[dict], *, central_headings: list[str],
                            draft: str, max_units: int = 16, max_evidence: int = 24,
                            policy_version: int = 1, excluded_headings: list[str] | None = None,
                            execution_context: dict | None = None) -> dict:
    """Select cited evidence by identity, never by its position in a global list."""
    records = {}
    for item in claims:
        if item.get("claim_id"):
            records.setdefault(str(item["claim_id"]), []).append(item)
    marker = r"\[\[@claim:([^\]]+)\]\]"
    draft_refs = list(dict.fromkeys(re.findall(marker, draft)))
    units, requested, findings, substantive = [], [], [], []
    execution_facts = {}
    heading = ""
    for index, paragraph in enumerate(section_text.split("\n\n")):
        lines = paragraph.splitlines()
        if lines and lines[0].startswith("## "):
            heading = lines[0][3:].strip()
            paragraph = "\n".join(lines[1:]).strip()
        refs = list(dict.fromkeys(re.findall(marker, paragraph)))
        if not paragraph or heading in (excluded_headings or []) or (policy_version < 2 and not refs and heading not in central_headings):
            continue
        if paragraph.startswith(("![", "[[figure:")) or (policy_version < 2 and paragraph.startswith("|")):
            continue
        identity = hashlib.sha256(f"{index}:{heading}:{paragraph}".encode()).hexdigest()[:20]
        context_refs = refs or draft_refs
        requested.extend(context_refs)
        if len(paragraph) > 4000:
            findings.append(f"Passage {identity} exceeds the evidence-review text limit.")
        from app.services.research_quality import guarantee_risks
        risks = guarantee_risks(paragraph) if policy_version >= 2 else []
        procedure = None
        if policy_version >= 4 and risks:
            from app.services.execution_evidence import execution_procedure_fact
            procedure = execution_procedure_fact(paragraph, execution_context)
        if procedure:
            execution_facts[procedure["fact_id"]] = procedure
        units.append({"statement_id": identity, "section": heading, "guarantee_risks": risks,
                      "passage": paragraph[:4000], "claim_ids": context_refs, "cited_claim_ids": refs,
                      "kind": "cited_passage" if refs else "interpretation"})
        if procedure and not refs:
            # Only this bounded procedural fact is supplied by execution. Other
            # scientific guarantees still require source context and assumptions.
            units[-1]["detected_guarantee_risks"] = risks
            units[-1]["guarantee_risks"] = []
            units[-1]["execution_fact_ids"] = [procedure["fact_id"]]
    if len(units) > max_units:
        findings.append("This batch exceeds the passage-review limit; unreviewed passages require review.")
    requested = list(dict.fromkeys(requested))
    if len(requested) > max_evidence:
        findings.append("This batch exceeds the evidence-context limit; do not infer complete support.")
    evidence = []
    candidates = []
    seen_evidence = set()
    for claim_id in requested:
        if claim_id not in records:
            findings.append(f"Claim {claim_id} is absent from supplied evidence.")
        for item in records.get(claim_id, []):
            key = (claim_id, item.get("evidence_id"), item.get("source_id"), item.get("chunk_id"),
                   item.get("evidence_quote") or item.get("evidence_text"))
            if key not in seen_evidence:
                candidates.append((claim_id, item))
                seen_evidence.add(key)
    # A claim may have several evidence/source records; retain them all within
    # the same bound rather than silently replacing earlier support.
    if len(candidates) > max_evidence:
        findings.append("Evidence record count exceeds the context limit.")
    for claim_id, item in candidates[:max_evidence]:
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
                         "evidence_need_id": str(item.get("evidence_need_id") or "")[:40],
                         "assumptions": [value[:300] for value in (item.get("assumptions") or [])[:8]
                                         if isinstance(value, str)],
                         **{k: item.get(k) for k in ("source_id", "chunk_id", "source_title", "text_scope", "source_type", "doi")}})
    for unit in units[:max_units]:
        if unit["guarantee_risks"]:
            full_context = [e for e in evidence if e["claim_id"] in unit["claim_ids"] and
                            (e.get("text_scope") in {"FULL_TEXT", "UPLOAD"} or e.get("source_type") == "PDF")]
            if not full_context:
                substantive.append(f"[{unit['section']}] A strong technical guarantee requires full-text context and explicit assumptions, or weaker wording: {unit['guarantee_risks'][0]}")
    return {"units": units[:max_units], "evidence": evidence, "coverage_findings": findings,
            "execution_facts": list(execution_facts.values()),
            "expected_units": len(units), "policy_version": policy_version, "substantive_findings": substantive}


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
        if prepared.get("policy_version", 1) >= 2 and review.judgment == "SUPPORTED":
            unit = next(u for u in prepared["units"] if u["statement_id"] == review.statement_id)
            valid_ids = {e["claim_id"] for e in prepared["evidence"]} & set(unit["claim_ids"])
            if (unit["cited_claim_ids"] and not review.supporting_claim_ids) or not set(review.supporting_claim_ids) <= valid_ids:
                findings.append(f"Support for {review.statement_id} lacks valid passage-specific evidence identities.")
            if unit.get("guarantee_risks") and not review.assumptions_preserved:
                findings.append(f"Assumptions were not checked for {review.statement_id}.")
            if prepared.get("policy_version", 1) >= 3:
                anchored_ids = set()
                for anchor in review.quote_anchors:
                    matches = [e for e in prepared["evidence"]
                               if e["claim_id"] == anchor.claim_id
                               and str(e.get("source_id")) == anchor.source_id
                               and str(e.get("chunk_id")) == anchor.chunk_id]
                    if (anchor.claim_id not in set(review.supporting_claim_ids) & valid_ids
                            or not anchor.quote.strip()
                            or not any(anchor.quote in e["quote"] for e in matches)):
                        findings.append(f"Quote anchor for {review.statement_id} is absent from its supplied source evidence.")
                    else:
                        anchored_ids.add(anchor.claim_id)
                if set(review.supporting_claim_ids) - anchored_ids:
                    findings.append(f"Support for {review.statement_id} lacks literal quote anchors for its declared evidence.")
                if set(unit["cited_claim_ids"]) - anchored_ids:
                    findings.append(f"Direct citations in {review.statement_id} were not all checked against literal source quotes.")
            if prepared.get("policy_version", 1) >= 4:
                expected_facts = set(unit.get("execution_fact_ids", []))
                declared_facts = set(review.supporting_execution_fact_ids)
                if declared_facts != expected_facts:
                    findings.append(f"Execution support for {review.statement_id} does not match its supplied procedure facts.")
    if expected - seen:
        findings.append(f"Missing support judgments for {len(expected - seen)} passages.")
    return {"expected_passages": prepared.get("expected_units", len(expected)), "reviewed_passages": len(seen),
            "coverage_complete": not findings, "findings": findings, "judgments": accepted,
            "substantive_findings": prepared.get("substantive_findings", []),
            "all_supported": not findings and not prepared.get("substantive_findings") and all(r["judgment"] == "SUPPORTED" for r in accepted)}


def audit_matches_draft(metadata: dict, draft: str) -> bool:
    audit = metadata.get("evidence_support_review") or {}
    return bool(audit.get("coverage_complete") and audit.get("all_supported")
                and audit.get("draft_sha256") == hashlib.sha256(draft.encode()).hexdigest())
