import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.user import User
from app.models.report import ResearchReport
from app.models.grounding import Citation
from app.models.source import DocumentChunk, ResearchSource
from app.schemas.task import ResearchTaskCreate, ResearchTaskResponse
from app.schemas.report import CitationItemResponse, ResearchReportResponse, ResearchSourceItemResponse

router = APIRouter()




@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_research_task(
    task_in: ResearchTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo mới một Research Task."""
    
    budget_dict = task_in.budget.model_dump() if task_in.budget else {
        "max_cost_usd": 2.0,
        "max_llm_calls": 50,
        "max_input_tokens": 100000,
        "max_output_tokens": 50000,
        "timeout_seconds": 300,
    }
    
    task = ResearchTask(
        user_id=current_user.id,
        title=task_in.title,
        research_question=task_in.research_question,
        description=task_in.description,
        research_depth=task_in.research_depth,
        language=task_in.language,
        max_sources=task_in.max_sources,
        max_iterations=task_in.max_iterations,
        report_length=task_in.report_length,
        citation_style=task_in.citation_style,
        budget_config=budget_dict,
        require_plan_approval=task_in.require_plan_approval,
        status="PENDING",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("", response_model=List[ResearchTaskResponse])
async def list_research_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Lấy danh sách các Research Task."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.user_id == current_user.id)
        .order_by(ResearchTask.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem thông tin chi tiết một Research Task."""
    result = await db.execute(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return task


@router.post("/{task_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bắt đầu hoặc chạy lại workflow nghiên cứu đa tác tử trong Celery background."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status not in ("PENDING", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"Research task cannot be started from status {task.status}")
    
    task.status = "QUEUED"
    task.completed_at = None
    task.worker_lease_until = None

    # Check if outbox item already exists (e.g. from previously cancelled task)
    outbox_res = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task.id,
            TaskDispatchOutbox.event_type == "START_RESEARCH"
        )
    )
    outbox_item = outbox_res.scalar_one_or_none()
    if outbox_item:
        outbox_item.dispatched_at = None
        outbox_item.locked_until = None
        outbox_item.last_error = None
        outbox_item.available_at = datetime.now(timezone.utc)
        outbox_item.attempts = 0
    else:
        db.add(TaskDispatchOutbox(research_task_id=task.id, event_type="START_RESEARCH"))

    await db.commit()

    return {"status": "QUEUED", "message": "Workflow accepted for dispatch", "task_id": str(task_id)}

@router.get("/{task_id}/report", response_model=ResearchReportResponse)
async def get_research_report(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy báo cáo kết quả của Research Task."""
    result = await db.execute(
        select(ResearchReport)
        .join(ResearchTask, ResearchReport.research_task_id == ResearchTask.id)
        .where(ResearchReport.research_task_id == task_id, ResearchTask.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this task")
    return report


@router.get("/{task_id}/citations", response_model=List[CitationItemResponse])
async def get_research_citations(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách trích dẫn và bằng chứng đã xác minh của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(Citation, ResearchSource, DocumentChunk)
        .outerjoin(ResearchSource, Citation.source_id == ResearchSource.id)
        .outerjoin(DocumentChunk, Citation.chunk_id == DocumentChunk.id)
        .where(Citation.research_task_id == task_id)
        .order_by(Citation.citation_number.asc().nulls_last(), Citation.id.asc())
    )
    rows = result.all()
    citations = []
    for cit, src, chk in rows:
        citations.append(
            CitationItemResponse(
                id=cit.id,
                citation_number=cit.citation_number,
                citation_label=cit.citation_label,
                claim_text=cit.claim_text,
                source_id=cit.source_id,
                source_title=src.title if src else None,
                source_url=src.url if src else "",
                chunk_id=cit.chunk_id,
                chunk_content=chk.content if chk else None,
            )
        )
    return citations


@router.get("/{task_id}/sources", response_model=List[ResearchSourceItemResponse])
async def get_research_sources(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các nguồn tài liệu đã thu thập của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(ResearchSource)
        .where(ResearchSource.research_task_id == task_id)
        .order_by(ResearchSource.relevance_score.desc(), ResearchSource.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hủy một Research Task đang chờ hoặc đang chạy."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED", "PARTIAL", "NEEDS_REVIEW"}
    if task.status in terminal_statuses:
        return {"status": task.status, "message": f"Task is already {task.status}", "task_id": str(task_id)}

    task.status = "CANCELLED"
    task.completed_at = datetime.now(timezone.utc)
    task.worker_lease_until = None

    # Cancel any pending outbox entry to prevent dispatch
    outbox_res = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task_id,
            TaskDispatchOutbox.dispatched_at.is_(None),
        )
    )
    for outbox_item in outbox_res.scalars().all():
        outbox_item.dispatched_at = datetime.now(timezone.utc)
        outbox_item.last_error = "Cancelled by user"

    await db.commit()

    # If capacity freed up, trigger next queued task for this user
    try:
        from app.services.task_dispatcher import dispatch_one_outbox_event
        await dispatch_one_outbox_event(user_id=current_user.id)
    except Exception:
        pass

    return {"status": "CANCELLED", "message": "Research task cancelled successfully", "task_id": str(task_id)}


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa một Research Task."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    await db.delete(task)
    await db.commit()
    return {"message": "Research task deleted successfully", "task_id": str(task_id)}


