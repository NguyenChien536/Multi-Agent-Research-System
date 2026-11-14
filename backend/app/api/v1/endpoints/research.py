import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.task import ResearchTask, TaskDispatchOutbox, DocumentIngestionOutbox, WorkflowRun
from app.models.user import User
from app.models.source import ResearchSource
from app.models.agent_run import AgentRun
from app.schemas.task import (
    ResearchTaskCreate,
    ResearchTaskResponse,
    TokenAllowanceIncrease,
)
from app.schemas.agent_run import AgentRunItemResponse

router = APIRouter()


@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_research_task(
    task_in: ResearchTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo mới một Research Task."""
    owner = await db.scalar(select(User).where(User.id == current_user.id, User.deleted_at.is_(None)).with_for_update(read=True))
    if owner is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    
    budget_dict = task_in.budget.model_dump() if task_in.budget else {
        "max_cost_usd": 2.0,
        "max_llm_calls": 40,
        "max_input_tokens": 100000,
        "max_output_tokens": 50000,
        "timeout_seconds": 900,
    }
    
    task = ResearchTask(
        id=uuid.uuid4(),
        user_id=current_user.id,
        title=task_in.title,
        research_question=task_in.research_question,
        description=task_in.description,
        research_type=task_in.research_type,
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
    connection_input = task_in.llm_connection
    if connection_input is None and task_in.use_saved_connection and current_user.model_connection:
        from app.services.user_model_settings import decode_input, settings_id
        try:
            connection_input = decode_input(current_user.model_connection, current_user.id, settings_id(current_user.id))
        except ValueError:
            raise HTTPException(409, 'Update your API connection in Settings before creating research') from None
    if connection_input is not None:
        from app.services.model_connection import seal_connection
        try:
            sealed = seal_connection(connection_input, task.id, current_user.id)
        except ValueError:
            raise HTTPException(503, "Private API connections are not configured securely on this server") from None
        task.budget_config = {**budget_dict, "_llm_connection": sealed}
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
        .where(ResearchTask.status != "DELETING")
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
    result = await db.execute(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING"))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    response = ResearchTaskResponse.model_validate(task)
    from app.services.public_errors import task_error_summary
    response.latest_error, response.failed_agent = await task_error_summary(db, task)
    return response


@router.post("/{task_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bắt đầu hoặc chạy lại workflow nghiên cứu đa tác tử trong Celery background."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status not in ("PENDING", "CANCELLED", "FAILED", "NEEDS_REVIEW"):
        raise HTTPException(status_code=409, detail=f"Research task cannot be started from status {task.status}")
    from app.services.provider_budget import retry_block_reason
    if retry_block_reason(task):
        raise HTTPException(409, 'TASK_BUDGET_LIMIT: This article cannot continue within its remaining allowance. Saved results are retained; create a new research article.')

    pending_ingestion = await db.scalar(
        select(func.count(ResearchSource.id)).where(
            ResearchSource.research_task_id == task.id,
            ResearchSource.source_type == "PDF",
            ResearchSource.ingestion_status.in_(("PENDING", "PROCESSING")),
        )
    )
    if pending_ingestion:
        raise HTTPException(status_code=409, detail="Tài liệu PDF vẫn đang được xử lý. Hãy đợi trạng thái READY rồi bắt đầu bài nghiên cứu.")
    
    # Older workers did not freeze the clock on terminal states. Do not charge
    # hours spent reading a finished report as active research on explicit retry.
    from app.services.provider_budget import pause_budget_config
    task.budget_config = pause_budget_config(task.budget_config, now=task.completed_at)
    task.budget_config = {key: value for key, value in task.budget_config.items() if key not in {'_writer_progress', '_provider_wait'}}
    task.status = "QUEUED"
    task.completed_at = None
    task.worker_lease_until = None
    task.current_iteration = 0
    task.current_step = None
    task.plan = None
    task.plan_approved = False
    task.plan_version = 0
    task.resume_action = None
    task.resume_payload = None

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
        outbox_item.unclaimed_retries = 0
    else:
        db.add(TaskDispatchOutbox(research_task_id=task.id, event_type="START_RESEARCH"))

    await db.commit()

    return {"status": "QUEUED", "message": "Workflow accepted for dispatch", "task_id": str(task_id)}


@router.post('/{task_id}/retry', status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_research(task_id: uuid.UUID, allowance: TokenAllowanceIncrease | None = Body(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Resume the owning failed run's durable checkpoint without repeating completed nodes."""
    task = await db.scalar(select(ResearchTask).where(ResearchTask.id == task_id,
        ResearchTask.user_id == current_user.id).with_for_update())
    if task is None or task.status == 'DELETING':
        raise HTTPException(404, 'Research task not found')
    budget_stopped = task.status == 'NEEDS_REVIEW' and task.current_step == 'BUDGET_LIMIT'
    if task.status != 'FAILED' and not (budget_stopped and allowance is not None):
        raise HTTPException(409, 'Only failed research can be retried from its saved step')
    from app.services.provider_budget import retry_block_reason, pause_budget_config, increase_token_allowance
    config = pause_budget_config(task.budget_config, now=task.completed_at)
    if allowance is not None:
        try:
            config = increase_token_allowance(config, allowance.max_input_tokens, allowance.max_output_tokens,
                max_llm_calls=allowance.max_llm_calls, timeout_seconds=allowance.timeout_seconds,
                max_cost_usd=allowance.max_cost_usd)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
    task.budget_config = config
    if retry_block_reason(task, ignore_stop_marker=allowance is not None):
        raise HTTPException(409, 'TASK_BUDGET_LIMIT: Remaining allowance is insufficient. Review token limits; cost, call and time limits still apply.')
    run = await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id == task.id
        ).order_by(WorkflowRun.run_number.desc()).limit(1).with_for_update())
    if run is None or run.status != ('NEEDS_REVIEW' if budget_stopped else 'FAILED'):
        raise HTTPException(409, 'No saved failed workflow is available; start a new research run instead')
    run.status, run.completed_at = 'RUNNING', None
    task.status, task.completed_at = 'QUEUED', None
    task.current_step = None
    task.worker_lease_until = None
    task.queued_at = datetime.now(timezone.utc)
    event = await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id == task.id,
        TaskDispatchOutbox.event_type == 'START_RESEARCH').with_for_update())
    if event is None:
        db.add(TaskDispatchOutbox(research_task_id=task.id, event_type='START_RESEARCH'))
    else:
        event.dispatched_at = event.locked_until = event.last_error = None
        event.available_at = datetime.now(timezone.utc)
        event.attempts = event.unclaimed_retries = 0
    await db.commit()
    return {'status':'QUEUED','task_id':str(task_id),'message':'Retry accepted from the saved workflow step'}

@router.post("/{task_id}/sources/{source_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_document_ingestion(
    task_id: uuid.UUID,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Requeue one failed private PDF ingestion for its owner."""
    task = await db.scalar(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status in {"RUNNING", "QUEUED", "COMPLETED", "FAILED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="Tài liệu chỉ có thể thử lại khi bài nghiên cứu chưa chạy.")
    source = await db.scalar(
        select(ResearchSource).where(
            ResearchSource.id == source_id,
            ResearchSource.research_task_id == task.id,
            ResearchSource.source_type == "PDF",
        ).with_for_update()
    )
    if not source:
        raise HTTPException(status_code=404, detail="PDF source not found")
    if source.ingestion_status != "FAILED":
        raise HTTPException(status_code=409, detail="Chỉ có thể thử lại tài liệu đang ở trạng thái FAILED.")
    source.ingestion_status = "PENDING"
    source.ingestion_error = None
    source.ingestion_lease_until = None
    source.ingestion_attempt = 0
    outbox = await db.scalar(
        select(DocumentIngestionOutbox).where(DocumentIngestionOutbox.source_id == source.id).with_for_update()
    )
    if outbox is None:
        outbox = DocumentIngestionOutbox(research_task_id=task.id, source_id=source.id)
        db.add(outbox)
    else:
        outbox.dispatched_at = None
        outbox.locked_until = None
        outbox.available_at = datetime.now(timezone.utc)
        outbox.last_error = None
        outbox.attempts = 0
        outbox.unclaimed_retries = 0
    await db.commit()
    return {"source_id": str(source.id), "ingestion_status": "PENDING"}


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hủy một Research Task đang chờ hoặc đang chạy."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
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
    from app.services.provider_budget import pause_budget_config
    task.budget_config = pause_budget_config(task.budget_config)
    active_run_res = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.research_task_id == task.id,
            WorkflowRun.status.in_(["RUNNING", "WAITING_APPROVAL", "WAITING_USER_DATA"]),
        ).with_for_update()
    )
    for workflow_run in active_run_res.scalars():
        workflow_run.status = "CANCELLED"
        workflow_run.completed_at = datetime.now(timezone.utc)

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


@router.delete("/{task_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hide a task immediately and queue durable private-artifact cleanup."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    if task.status == "DELETING":
        return {"status": "DELETING", "message": "Task deletion is already queued", "task_id": str(task_id)}
    from app.services.account_deletion import tombstone_task
    await tombstone_task(db, task)
    await db.commit()
    return {"status": "DELETING", "message": "Task hidden; cleanup queued", "task_id": str(task_id)}


@router.get("/{task_id}/agent-runs", response_model=List[AgentRunItemResponse])
async def get_task_agent_runs(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy lịch sử thực thi của các Agent trong Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.research_task_id == task_id)
        .order_by(AgentRun.started_at.asc(), AgentRun.id.asc())
    )
    return result.scalars().all()
