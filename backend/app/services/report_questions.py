import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grounding import Citation
from app.models.report import ResearchReport, ReportVersion
from app.models.report_question import ReportQuestion
from app.models.source import DocumentChunk, ResearchSource
from app.models.task import ResearchTask
from app.models.user import User
from app.schemas.report_question import ReportQuestionCreate
from app.services.provider_budget import ProviderBudgetExceeded, ResearchTaskStopped
from app.services.report_question_answering import (
    INSUFFICIENT_ANSWER, QA_TIMEOUT_SECONDS, InvalidAnswer, bounded_excerpt, generate_answer, terms,
)

logger = logging.getLogger(__name__)
POST_RUN_STATUSES = {"COMPLETED", "NEEDS_REVIEW", "PARTIAL"}
MAX_QUESTIONS_PER_TASK = 50
QUESTION_LEASE_SECONDS = 75


async def owned_version(db: AsyncSession, task_id: uuid.UUID, version_number: int,
                        user_id: uuid.UUID, lock: bool = False):
    query = (select(ResearchTask, ReportVersion).join(ResearchReport, ResearchReport.research_task_id == ResearchTask.id)
             .join(ReportVersion, ReportVersion.report_id == ResearchReport.id)
             .where(ResearchTask.id == task_id, ResearchTask.user_id == user_id,
                    ResearchTask.status != "DELETING", ReportVersion.version_number == version_number))
    if lock:
        query = query.with_for_update(of=ResearchTask).execution_options(populate_existing=True)
    row = (await db.execute(query)).one_or_none()
    if row is None:
        raise HTTPException(404, "Report version not found")
    return row


async def expire_questions(db: AsyncSession, user_id: uuid.UUID):
    await db.execute(update(ReportQuestion).where(
        ReportQuestion.user_id == user_id, ReportQuestion.status == "RUNNING",
        ReportQuestion.expires_at <= datetime.now(timezone.utc),
    ).values(status="FAILED", error_code="INTERRUPTED", completed_at=datetime.now(timezone.utc)))


async def build_context(db: AsyncSession, task: ResearchTask, version: ReportVersion, question: str):
    rows = (await db.execute(select(Citation.id, ResearchSource.title, ResearchSource.url,
        func.left(DocumentChunk.content, 8000).label("content"))
        .join(ResearchSource, ResearchSource.id == Citation.source_id)
        .join(DocumentChunk, DocumentChunk.id == Citation.chunk_id)
        .where(Citation.report_version_id == version.id, Citation.report_id == version.report_id,
               Citation.research_task_id == task.id, ResearchSource.research_task_id == task.id,
               DocumentChunk.research_task_id == task.id, DocumentChunk.source_id == Citation.source_id)
        .order_by(Citation.citation_number.asc().nulls_last(), Citation.id.asc()).limit(101))).all()
    candidates = [row for row in rows[:100] if row.content and row.content.strip()]
    words = terms(question)
    candidates.sort(key=lambda row: -len(words & terms(row.content)))
    evidence = [{"citation_id": str(row.id), "title": (row.title or "")[:300], "url": row.url[:2000],
                 "excerpt": bounded_excerpt(row.content, question, 1200)} for row in candidates[:8]]
    article = bounded_excerpt(version.content_markdown, question, 8000)
    context = {"version_number": version.version_number, "article_excerpt": article, "evidence": evidence}
    truncated = len(rows) > 8 or len(version.content_markdown) > 8000 or any(len(row.content) > 1200 for row in candidates[:8])
    return context, truncated


async def ask_question(db: AsyncSession, task_id: uuid.UUID, version_number: int,
                       user_id: uuid.UUID, payload: ReportQuestionCreate):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    task, version = await owned_version(db, task_id, version_number, user_id, lock=True)
    await expire_questions(db, user_id)
    existing = await db.scalar(select(ReportQuestion).where(
        ReportQuestion.user_id == user_id, ReportQuestion.request_id == payload.request_id))
    if existing:
        if existing.report_version_id != version.id or existing.question != payload.question:
            raise HTTPException(409, "Request ID already belongs to a different question or version")
        await db.commit()
        return existing
    if task.status not in POST_RUN_STATUSES:
        raise HTTPException(409, "Questions are available after the research run finishes")
    if await db.scalar(select(ReportQuestion.id).where(ReportQuestion.user_id == user_id,
                                                      ReportQuestion.status == "RUNNING").limit(1)):
        raise HTTPException(409, "A question is already being answered; wait before asking another")
    total = await db.scalar(select(func.count(ReportQuestion.id)).join(ReportVersion)
                           .join(ResearchReport).where(ResearchReport.research_task_id == task_id))
    if total >= MAX_QUESTIONS_PER_TASK:
        raise HTTPException(429, "Question history limit reached for this article (50)")
    context, truncated = await build_context(db, task, version, payload.question)
    now = datetime.now(timezone.utc)
    question = ReportQuestion(user_id=user_id, report_version_id=version.id,
        request_id=payload.request_id, question=payload.question, status="RUNNING", references=[],
        context_hash=hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest(),
        context_truncated=truncated, expires_at=now + timedelta(seconds=QUESTION_LEASE_SECONDS))
    if not context["evidence"]:
        question.status = "INSUFFICIENT_EVIDENCE"
        question.answer = INSUFFICIENT_ANSWER
        question.completed_at = now
    db.add(question)
    await db.commit()
    question_id, attempt_number = question.id, task.attempt_number
    if question.status != "RUNNING":
        logger.info("Report question finished task=%s question=%s version=%s status=%s",
                    task_id, question_id, version.id, question.status)
        return question
    status, answer, references, error_code = "FAILED", None, [], None
    try:
        async with asyncio.timeout(QA_TIMEOUT_SECONDS):
            status, answer, references = await generate_answer(task_id, attempt_number, question_id, payload.question, context)
    except ProviderBudgetExceeded:
        status, error_code = "BUDGET_LIMIT", "BUDGET_LIMIT"
    except ResearchTaskStopped:
        error_code = "TASK_CHANGED"
    except TimeoutError:
        error_code = "TIMEOUT"
    except InvalidAnswer:
        error_code = "INVALID_REFERENCE"
    except asyncio.CancelledError:
        # The persisted lease/history lets the next read recover an interrupted HTTP request.
        raise
    except Exception as exc:
        error_code = "PROVIDER_ERROR"
        logger.warning("Question failed task=%s question=%s error_type=%s", task_id, question_id, type(exc).__name__)
    # Recheck tombstone, attempt and the question lease after the external request.
    # No task/report row lock was held while waiting for a provider.
    current_task, _ = await owned_version(db, task_id, version_number, user_id, lock=True)
    await db.refresh(question, with_for_update=True)
    if question.status == "RUNNING":
        if current_task.status not in POST_RUN_STATUSES or current_task.attempt_number != attempt_number:
            status, answer, references, error_code = "FAILED", None, [], "TASK_CHANGED"
        elif question.expires_at <= datetime.now(timezone.utc):
            status, answer, references, error_code = "FAILED", None, [], "INTERRUPTED"
        question.status, question.answer, question.references = status, answer, references
        question.error_code, question.completed_at = error_code, datetime.now(timezone.utc)
        await db.commit()
    logger.info("Report question finished task=%s question=%s version=%s status=%s error_code=%s",
                task_id, question_id, version.id, question.status, question.error_code)
    return question
