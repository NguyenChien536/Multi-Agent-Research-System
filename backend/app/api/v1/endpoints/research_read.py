"""Read-only report, version, citation, and source endpoints."""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.task import ResearchTask
from app.models.report import ResearchReport, ReportVersion
from app.models.grounding import Citation
from app.models.source import DocumentChunk, ResearchSource
from app.schemas.report import CitationItemResponse, ResearchReportResponse, ResearchSourceItemResponse

router = APIRouter()

@router.get("/{task_id}/report", response_model=ResearchReportResponse)
async def get_research_report(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest immutable report version for backward compatibility."""
    report = await db.scalar(
        select(ResearchReport)
        .join(ResearchTask, ResearchReport.research_task_id == ResearchTask.id)
        .where(ResearchReport.research_task_id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this task")
    version = await db.scalar(
        select(ReportVersion)
        .where(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Report version not found for this task")
    return _report_response(report, version)


def _report_response(report: ResearchReport, version: ReportVersion) -> ResearchReportResponse:
    return ResearchReportResponse(
        id=report.id,
        research_task_id=report.research_task_id,
        version_id=version.id,
        version_number=version.version_number,
        workflow_run_id=version.workflow_run_id,
        plan_version=version.plan_version,
        title=version.title,
        content_markdown=version.content_markdown,
        executive_summary=version.executive_summary,
        review_status=version.review_status,
        review_metadata=version.review_metadata,
        word_count=version.word_count,
        created_at=version.created_at,
        updated_at=version.created_at,
    )


async def _get_owned_report(
    db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID
) -> ResearchReport | None:
    return await db.scalar(
        select(ResearchReport)
        .join(ResearchTask, ResearchReport.research_task_id == ResearchTask.id)
        .where(
            ResearchReport.research_task_id == task_id,
            ResearchTask.user_id == user_id,
            ResearchTask.status != "DELETING",
        )
    )


@router.get("/{task_id}/report/versions", response_model=List[ResearchReportResponse])
async def list_report_versions(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.scalar(
        select(ResearchTask).where(
            ResearchTask.id == task_id,
            ResearchTask.user_id == current_user.id,
            ResearchTask.status != "DELETING",
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    report = await _get_owned_report(db, task_id, current_user.id)
    if report is None:
        return []
    versions = await db.scalars(
        select(ReportVersion)
        .where(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version_number.desc())
    )
    return [_report_response(report, version) for version in versions.all()]


@router.get("/{task_id}/report/versions/{version_number}", response_model=ResearchReportResponse)
async def get_report_version(
    task_id: uuid.UUID,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await _get_owned_report(db, task_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found for this task")
    version = await db.scalar(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Report version not found")
    return _report_response(report, version)


async def _get_version_citations(
    db: AsyncSession, task_id: uuid.UUID, version_id: uuid.UUID
) -> List[CitationItemResponse]:
    rows = (await db.execute(
        select(Citation, ResearchSource, DocumentChunk)
        .outerjoin(ResearchSource, Citation.source_id == ResearchSource.id)
        .outerjoin(DocumentChunk, Citation.chunk_id == DocumentChunk.id)
        .where(
            Citation.research_task_id == task_id,
            Citation.report_version_id == version_id,
        )
        .order_by(Citation.citation_number.asc().nulls_last(), Citation.id.asc())
    )).all()
    return [
        CitationItemResponse(
            id=citation.id,
            report_version_id=citation.report_version_id,
            citation_number=citation.citation_number,
            citation_label=citation.citation_label,
            claim_text=citation.claim_text,
            source_id=citation.source_id,
            source_title=source.title if source else None,
            source_url=source.url if source else "",
            chunk_id=citation.chunk_id,
            chunk_content=chunk.content if chunk else None,
        )
        for citation, source, chunk in rows
    ]


@router.get(
    "/{task_id}/report/versions/{version_number}/citations",
    response_model=List[CitationItemResponse],
)
async def get_report_version_citations(
    task_id: uuid.UUID,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await _get_owned_report(db, task_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found for this task")
    version_id = await db.scalar(
        select(ReportVersion.id).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version_number == version_number,
        )
    )
    if version_id is None:
        raise HTTPException(status_code=404, detail="Report version not found")
    return await _get_version_citations(db, task_id, version_id)


@router.get("/{task_id}/citations", response_model=List[CitationItemResponse])
async def get_research_citations(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách trích dẫn và bằng chứng đã xác minh của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    latest_version_id = await db.scalar(
        select(ReportVersion.id)
        .join(ResearchReport, ResearchReport.id == ReportVersion.report_id)
        .where(ResearchReport.research_task_id == task_id)
        .order_by(ReportVersion.version_number.desc())
        .limit(1)
    )
    if latest_version_id is None:
        return []
    return await _get_version_citations(db, task_id, latest_version_id)


@router.get("/{task_id}/sources", response_model=List[ResearchSourceItemResponse])
async def get_research_sources(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các nguồn tài liệu đã thu thập của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(ResearchSource)
        .where(ResearchSource.research_task_id == task_id)
        .order_by(ResearchSource.relevance_score.desc(), ResearchSource.created_at.asc())
    )
    return result.scalars().all()
