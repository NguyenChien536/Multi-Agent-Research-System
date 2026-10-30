"""Editorial revisions reuse frozen inputs; they never discover data or execute experiments."""
from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.models.grounding import Citation, ClaimEvidence, Evidence, ResearchClaim
from app.models.report import ResearchReport, ReportVersion
from app.models.report_revision import ReportRevision
from app.models.source import DocumentChunk, ResearchSource
from app.models.task import TaskDispatchOutbox
from app.services.report_questions import owned_version, POST_RUN_STATUSES

ACTIVE = {"QUEUED", "RUNNING"}
MAX_REVISIONS = 30
REVISION_READY = POST_RUN_STATUSES | {"FAILED", "CANCELLED"}


async def reconcile_revisions(db, task):
    requests = (await db.scalars(select(ReportRevision).where(
        ReportRevision.research_task_id == task.id, ReportRevision.status.in_(ACTIVE)
    ).with_for_update())).all()
    pending_id = str((task.resume_payload or {}).get("revision_id", ""))
    for request in requests:
        if task.status in {"QUEUED", "RUNNING"} and task.resume_action == "REVISE_REPORT" and pending_id == str(request.id):
            continue
        request.status = "CANCELLED" if task.status == "CANCELLED" else "FAILED"
        request.error_code = "CANCELLED" if task.status == "CANCELLED" else (
            "BUDGET_LIMIT" if task.current_step == "BUDGET_LIMIT" else "TASK_CHANGED")
        request.completed_at = datetime.now(timezone.utc)
    await db.flush()


async def revision_inputs(db, task, base):
    """Rehydrate only source/claim chains explicitly cited by the selected version."""
    if not await db.scalar(select(ResearchReport.id).where(ResearchReport.id == base.report_id,
                                                         ResearchReport.research_task_id == task.id)):
        raise HTTPException(409, "The base report does not belong to this article")
    meta = base.review_metadata or {}
    contract = meta.get("manuscript_contract") or {}
    if not contract.get("sections") or len(base.content_markdown) > 60000:
        raise HTTPException(409, "This report lacks a supported manuscript snapshot or exceeds the editorial size limit; create a new research run")
    snapshot = meta.get("manuscript_input_snapshot") or {}
    research_type = {"NARRATIVE_REVIEW":"REVIEW", "COMPUTATIONAL_STUDY":"EMPIRICAL_COMPUTATIONAL", "EMPIRICAL_STUDY":"EMPIRICAL_HUMAN"}.get(contract.get("article_type"))
    if not research_type or snapshot.get("research_type", research_type) != research_type:
        raise HTTPException(409, "The base manuscript type cannot be established")
    analysis = deepcopy(snapshot.get("analysis_run") or (meta.get("scientific_context") or {}).get("analysis"))
    human_data = deepcopy(snapshot.get("user_data_submission"))
    if research_type == "EMPIRICAL_COMPUTATIONAL" and (not analysis or analysis.get("status") != "COMPLETED"):
        raise HTTPException(409, "The base version has no frozen completed analysis; a new research run is required")
    if research_type == "EMPIRICAL_HUMAN" and not human_data:
        raise HTTPException(409, "The base version has no frozen fieldwork input; a new research run is required")
    citations = (await db.scalars(select(Citation).where(Citation.report_version_id == base.id,
        Citation.report_id == base.report_id, Citation.research_task_id == task.id)
        .order_by(Citation.citation_number, Citation.id).limit(201))).all()
    if not citations or len(citations) > 200:
        raise HTTPException(409, "The base version needs valid, bounded source citations before it can be revised")
    rows = (await db.execute(select(Citation, ResearchClaim, Evidence, DocumentChunk, ResearchSource)
        .join(ResearchClaim, ResearchClaim.id == Citation.claim_id)
        .join(ClaimEvidence, ClaimEvidence.claim_id == ResearchClaim.id)
        .join(Evidence, Evidence.id == ClaimEvidence.evidence_id)
        .join(DocumentChunk, DocumentChunk.id == Citation.chunk_id)
        .join(ResearchSource, ResearchSource.id == Citation.source_id)
        .where(Citation.report_version_id == base.id, Citation.research_task_id == task.id,
            ResearchClaim.research_task_id == task.id, ResearchClaim.is_verified.is_(True),
            Evidence.research_task_id == task.id, Evidence.chunk_id == Citation.chunk_id,
            Evidence.source_id == Citation.source_id, DocumentChunk.source_id == Citation.source_id,
            DocumentChunk.research_task_id == task.id, ResearchSource.research_task_id == task.id)
        .order_by(Citation.citation_number, Citation.id))).all()
    claims, sources, valid_citations, label_markers = {}, {}, set(), {}
    frozen_bib = {(item.get("source_id"), item.get("citation_label")): item for item in meta.get("bibliography_snapshot", [])}
    for citation, claim, evidence, chunk, source in rows:
        if not evidence.content.strip() or evidence.content not in chunk.content:
            continue
        valid_citations.add(citation.id)
        description = frozen_bib.get((str(source.id), citation.citation_label), {})
        claims[str(claim.id)] = {"claim_id": str(claim.id), "claim": claim.claim_text,
            "evidence_id": str(evidence.id), "evidence_quote": evidence.content,
            "chunk_id": str(chunk.id), "source_id": str(source.id), "source_tag": source.source_tag,
            "source_title": description.get("source_title", source.title),
            "source_url": description.get("source_url", source.url),
            "source_author": description.get("source_author", source.author),
            "publication_date": description.get("publication_date", source.publication_date),
            "source_type": source.source_type,
            "doi": description.get("doi", source.doi),
            "venue": description.get("venue", source.venue),
            "search_provider": source.search_provider,
            "text_scope": source.text_scope}
        sources[str(source.id)] = {"db_id":str(source.id),"source_tag":source.source_tag,
            "title":source.title,"url":source.url,"source_type":source.source_type,
            "doi":source.doi,"venue":source.venue,"search_provider":source.search_provider,
            "full_text_url":source.full_text_url,"text_scope":source.text_scope}
        label_markers.setdefault(citation.citation_label, []).append(f"[[@claim:{claim.id}]]")
    if valid_citations != {item.id for item in citations}:
        raise HTTPException(409, "A base citation no longer has verified, owner-scoped evidence")
    if sum(len(str(c)) for c in claims.values()) > 100000:
        raise HTTPException(409, "The base evidence exceeds the editorial context limit")
    # Strip the generated bibliography before restoring each existing label to
    # its original claim marker(s). Do not use mutable citations from another version.
    heading = re.escape(contract.get("references_heading", "References"))
    draft = re.split(rf"(?m)^##\s+{heading}\s*$", base.content_markdown)[0].rstrip()
    pattern = "|".join(re.escape(label) for label in sorted(label_markers, key=len, reverse=True) if label)
    if pattern:
        draft = re.sub(pattern, lambda match: "".join(dict.fromkeys(label_markers[match[0]])), draft)
    provenance = deepcopy(meta.get("method_provenance") or {})
    plan = deepcopy(snapshot.get("plan") or {})
    plan["manuscript_contract"] = deepcopy(contract)
    plan["required_sections"] = [s["heading"] for s in contract["sections"]]
    return {"editorial_revision": True, "base_report_markdown": draft,
        "source_provenance": provenance, "research_type":research_type,
        "language":contract.get("language", task.language),
        "citation_style":snapshot.get("citation_style", task.citation_style),
        "report_length":snapshot.get("report_length", task.report_length),
        "plan":plan,"plan_version":base.plan_version or 0,"plan_approved":True,
        "protocol":deepcopy(snapshot.get("protocol") or {}),"user_data_submission":human_data,
        "analysis_run":analysis,"claims":list(claims.values()),"collected_sources":list(sources.values()),
        "dataset_csv":None,"dataset_artifact_id":None,"current_iteration":0,"max_iterations":0,
        "search_activity":deepcopy(provenance.get("search_activity_this_run", [])),
        "current_micro_revision":0,"critic_feedback":[],"critic_review_metadata":{}}


async def create_revision(db, task_id, version_number, user_id, payload):
    task, base = await owned_version(db, task_id, version_number, user_id, lock=True)
    await reconcile_revisions(db, task)
    previous = await db.scalar(select(ReportRevision).where(ReportRevision.user_id == user_id,
                                                          ReportRevision.request_id == payload.request_id))
    if previous:
        if previous.base_version_id != base.id or previous.instructions != payload.instructions:
            raise HTTPException(409, "Request ID already belongs to a different revision")
        await db.commit()
        return previous
    if task.status not in REVISION_READY:
        raise HTTPException(409, "Finish or cancel the current research operation before requesting an editorial revision")
    latest = await db.scalar(select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == base.report_id))
    if latest != version_number:
        raise HTTPException(409, "A newer report version exists; select the latest version before editing")
    if await db.scalar(select(func.count(ReportRevision.id)).where(ReportRevision.research_task_id == task.id)) >= MAX_REVISIONS:
        raise HTTPException(429, "Editorial revision limit reached for this article (30)")
    await revision_inputs(db, task, base)
    request = ReportRevision(user_id=user_id,research_task_id=task.id,base_version_id=base.id,
        request_id=payload.request_id,instructions=payload.instructions,status="QUEUED")
    db.add(request)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Another revision request already owns this identity or article") from exc
    from app.services.provider_budget import pause_budget_config
    task.budget_config = pause_budget_config(task.budget_config, now=task.completed_at)
    task.status, task.current_step, task.completed_at = "QUEUED", None, None
    task.worker_lease_until, task.queued_at = None, datetime.now(timezone.utc)
    task.resume_action, task.resume_payload = "REVISE_REPORT", {"revision_id":str(request.id)}
    event = await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id == task.id,
        TaskDispatchOutbox.event_type == "START_RESEARCH").with_for_update())
    if event is None:
        event = TaskDispatchOutbox(research_task_id=task.id,event_type="START_RESEARCH"); db.add(event)
    event.dispatched_at, event.locked_until, event.last_error = None, None, None
    event.available_at, event.attempts, event.unclaimed_retries = datetime.now(timezone.utc), 0, 0
    await db.commit()
    return request


async def prepare_revision(db, task, run):
    """Worker admission, preserving the same request/run across redelivery."""
    if task.resume_action != "REVISE_REPORT":
        return None, {}
    try:
        request_id = uuid.UUID((task.resume_payload or {})["revision_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Missing editorial request identity") from exc
    request = await db.scalar(select(ReportRevision).where(ReportRevision.id == request_id,
        ReportRevision.research_task_id == task.id,ReportRevision.user_id == task.user_id,
        ReportRevision.status.in_(ACTIVE)).with_for_update())
    if request is None or request.workflow_run_id not in (None, run.id):
        raise RuntimeError("Editorial request does not match the active workflow")
    base = await db.scalar(select(ReportVersion).join(ResearchReport).where(
        ReportVersion.id == request.base_version_id,ResearchReport.research_task_id == task.id))
    latest = await db.scalar(select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == base.report_id)) if base else None
    if base is None or latest != base.version_number:
        raise RuntimeError("The editorial base version is no longer current")
    initial = await revision_inputs(db, task, base)
    initial["revision_instructions"] = request.instructions
    initial["revision_info"] = {"revision_id":str(request.id),"base_version_id":str(base.id),
        "base_version_number":base.version_number,"kind":"EDITORIAL"}
    request.workflow_run_id, request.status = run.id, "RUNNING"
    await db.commit()
    return request, initial
