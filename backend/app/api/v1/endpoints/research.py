import os
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.task import ResearchTask, TaskDispatchOutbox, DocumentIngestionOutbox, TaskDeletionOutbox, WorkflowRun
from app.models.user import User
from app.models.report import ExportArtifact, ResearchReport
from app.models.grounding import Citation
from app.models.source import DocumentChunk, ResearchSource
from app.models.agent_run import AgentRun
from app.schemas.task import (
    ResearchTaskCreate,
    ResearchTaskResponse,
    PlanReviewResponse,
    PlanApprovalRequest,
    PlanRejectRequest,
    UserDataResumeRequest,
    ProtocolResponse,
)
from app.schemas.report import CitationItemResponse, ResearchReportResponse, ResearchSourceItemResponse
from app.schemas.agent_run import AgentRunItemResponse
from app.schemas.artifact import ArtifactItemResponse, PdfUploadResponse, FieldworkUploadResponse
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.schemas.experiment import (
    AnalysisRunResponse,
    ExperimentJournalEntryResponse,
    DatasetUploadResponse,
)
from app.services.experiment_runner import MAX_DATASET_BYTES, parse_csv_dataset, InvalidInputError
from app.services.artifact_store import artifact_store
from app.services.pdf_parser import (
    validate_pdf_bytes,
    PdfSizeLimitError,
    PdfValidationError,
)
from app.services.upload_reader import read_upload_with_limit, UploadSizeLimitExceeded
from app.services.fieldwork_intake import MAX_RESULT_BYTES, RESULT_TYPES, validate_fieldwork_result

router = APIRouter()


async def _require_active_workflow_run(db: AsyncSession, task: ResearchTask, expected_status: str) -> WorkflowRun:
    run = await db.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.research_task_id == task.id,
            WorkflowRun.status == expected_status,
        )
        .order_by(WorkflowRun.run_number.desc())
        .limit(1)
        .with_for_update()
    )
    if run is None:
        raise HTTPException(
            status_code=409,
            detail="This task has no resumable checkpoint. Restart the research task to create a new run.",
        )
    if run.plan_version != task.plan_version:
        raise HTTPException(status_code=409, detail="The saved checkpoint belongs to an older plan version.")
    return run




@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_research_task(
    task_in: ResearchTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo mới một Research Task."""
    
    budget_dict = task_in.budget.model_dump() if task_in.budget else {
        "max_cost_usd": 2.0,
        "max_llm_calls": 40,
        "max_input_tokens": 100000,
        "max_output_tokens": 50000,
        "timeout_seconds": 900,
    }
    
    task = ResearchTask(
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
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status not in ("PENDING", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"Research task cannot be started from status {task.status}")

    pending_ingestion = await db.scalar(
        select(func.count(ResearchSource.id)).where(
            ResearchSource.research_task_id == task.id,
            ResearchSource.source_type == "PDF",
            ResearchSource.ingestion_status.in_(("PENDING", "PROCESSING")),
        )
    )
    if pending_ingestion:
        raise HTTPException(status_code=409, detail="Tài liệu PDF vẫn đang được xử lý. Hãy đợi trạng thái READY rồi bắt đầu bài nghiên cứu.")
    
    task.status = "QUEUED"
    task.completed_at = None
    task.worker_lease_until = None
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
        .where(ResearchReport.research_task_id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
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
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
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
    task.status = "DELETING"
    task.deleted_at = datetime.now(timezone.utc)
    from app.services.provider_budget import pause_budget_config
    task.budget_config = pause_budget_config(task.budget_config)
    active_runs = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.research_task_id == task.id,
            WorkflowRun.status.in_(["RUNNING", "WAITING_APPROVAL", "WAITING_USER_DATA"]),
        ).with_for_update()
    )
    for workflow_run in active_runs.scalars():
        workflow_run.status = "CANCELLED"
        workflow_run.completed_at = datetime.now(timezone.utc)
    pending_dispatches = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task.id,
            TaskDispatchOutbox.dispatched_at.is_(None),
        ).with_for_update()
    )
    for event in pending_dispatches.scalars():
        event.dispatched_at = datetime.now(timezone.utc)
        event.last_error = "Task deleted by owner"
    deletion_outbox = await db.scalar(
        select(TaskDeletionOutbox).where(TaskDeletionOutbox.research_task_id == task.id).with_for_update()
    )
    if deletion_outbox is None:
        db.add(TaskDeletionOutbox(research_task_id=task.id))
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


@router.post("/{task_id}/upload", response_model=PdfUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_task_pdf(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lưu PDF riêng tư và xếp hàng xử lý nền; nguồn chỉ dùng được sau khi ingestion READY.
    """
    # 1. Kiểm tra quyền sở hữu task
    task_res = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = task_res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    if task.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ có thể thêm PDF khi bài nghiên cứu chưa được đưa vào hàng đợi.",
        )

    # 2. Kiểm tra giới hạn số file per task (tối đa 5 file theo SRS FR-02)
    existing_pdfs_res = await db.execute(
        select(func.count(ResearchSource.id)).where(
            ResearchSource.research_task_id == task_id,
            ResearchSource.source_type == "PDF",
        )
    )
    existing_pdf_count = existing_pdfs_res.scalar_one()
    if existing_pdf_count >= settings.MAX_UPLOAD_FILES_PER_TASK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vượt quá số lượng file tối đa cho một nghiên cứu (tối đa {settings.MAX_UPLOAD_FILES_PER_TASK} file/task).",
        )

    # 3. Đọc dữ liệu file
    try:
        content = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    except UploadSizeLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dung lượng file vượt quá giới hạn cho phép (tối đa {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MiB).",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lỗi khi đọc file tải lên: {e}")

    # Validate format/size cheaply; expensive parsing and chunking run in Celery.
    try:
        validate_pdf_bytes(content)
    except PdfSizeLimitError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except PdfValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 5. Lưu file vật lý an toàn vào ArtifactStore
    filename = file.filename or "document.pdf"
    artifact_meta = artifact_store.save_artifact(task_id=task.id, filename=filename, content=content)

    try:
        # Artifact/source metadata and the durable outbox commit atomically.
        artifact = ExportArtifact(
            research_task_id=task.id,
            export_type="PDF_UPLOAD",
            file_path=artifact_meta["file_path"],
            file_size_bytes=artifact_meta["file_size_bytes"],
            download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
        )
        db.add(artifact)
        await db.flush()
        artifact.download_url = f"/api/v1/research/{task.id}/artifacts/{artifact.id}/download"

        all_sources_res = await db.execute(
            select(func.count(ResearchSource.id)).where(ResearchSource.research_task_id == task.id)
        )
        total_sources = all_sources_res.scalar_one()
        source_tag = f"src_{total_sources + 1:02d}"
        db_source = ResearchSource(
            research_task_id=task.id,
            source_tag=source_tag,
            title=artifact_meta["file_name"],
            url=f"file://{artifact_meta['file_name']}",
            source_type="PDF",
            summary=f"PDF đang chờ xử lý nền ({artifact_meta['file_size_bytes']} bytes). SHA256: {artifact_meta['sha256_hash'][:16]}...",
            relevance_score=1.0,
            ingestion_status="PENDING",
            upload_artifact_id=artifact.id,
            content_checksum=artifact_meta["sha256_hash"],
        )
        db.add(db_source)
        await db.flush()
        db.add(DocumentIngestionOutbox(research_task_id=task.id, source_id=db_source.id))
        await db.commit()
    except Exception:
        await db.rollback()
        artifact_store.delete_artifact(task.id, artifact_meta["file_name"])
        raise

    return PdfUploadResponse(
        artifact_id=artifact.id,
        source_id=db_source.id,
        source_tag=source_tag,
        file_name=artifact_meta["file_name"],
        file_size_bytes=artifact_meta["file_size_bytes"],
        ingestion_status="PENDING",
        page_count=None,
        chunks_count=None,
        sha256_hash=artifact_meta["sha256_hash"],
        message="Đã lưu tài liệu. Hệ thống đang xử lý nội dung ở chế độ nền.",
    )


@router.get("/{task_id}/artifacts", response_model=List[ArtifactItemResponse])
async def list_task_artifacts(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các tệp tin / tài liệu riêng tư của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(ExportArtifact)
        .where(ExportArtifact.research_task_id == task_id)
        .order_by(ExportArtifact.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{task_id}/artifacts/{artifact_id}/download")
async def download_task_artifact(
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tải xuống tệp tin riêng tư của Research Task (chỉ dành cho chủ sở hữu)."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    artifact_res = await db.execute(
        select(ExportArtifact).where(
            ExportArtifact.id == artifact_id,
            ExportArtifact.research_task_id == task_id,
        )
    )
    artifact = artifact_res.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = artifact_store.get_artifact_path(task_id, artifact.file_path)
    if not file_path:
        raise HTTPException(status_code=404, detail="Artifact file does not exist on disk")

    media_type = "application/octet-stream"
    fp_lower = artifact.file_path.lower()
    if fp_lower.endswith(".pdf"):
        media_type = "application/pdf"
    elif fp_lower.endswith(".json"):
        media_type = "application/json"
    elif fp_lower.endswith(".csv"):
        media_type = "text/csv"
    elif fp_lower.endswith(".md"):
        media_type = "text/markdown"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=os.path.basename(artifact.file_path),
    )


@router.get("/{task_id}/plan", response_model=PlanReviewResponse)
async def get_research_plan(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem kế hoạch nghiên cứu do Supervisor tạo ra."""
    result = await db.execute(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    return PlanReviewResponse(
        task_id=task.id,
        status=task.status,
        require_plan_approval=task.require_plan_approval,
        plan_approved=task.plan_approved,
        plan_version=task.plan_version,
        plan=task.plan,
        plan_feedback=task.plan_feedback,
    )


@router.post("/{task_id}/plan/approve", response_model=ResearchTaskResponse)
async def approve_research_plan(
    task_id: uuid.UUID,
    payload: PlanApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Người dùng duyệt kế hoạch nghiên cứu và tiếp tục workflow."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail=f"Kế hoạch chỉ có thể duyệt khi task ở trạng thái WAITING_APPROVAL (hiện tại: {task.status})",
        )
    if payload.plan_version != task.plan_version:
        raise HTTPException(status_code=409, detail="This approval refers to an outdated plan version. Reload the current plan.")
    workflow_run = await _require_active_workflow_run(db, task, "WAITING_APPROVAL")

    # Nếu người dùng có chỉnh sửa search queries
    updated_plan = dict(task.plan or {})
    if payload.approved_queries and task.plan:
        updated_plan["search_queries"] = payload.approved_queries
    decision_id = uuid.uuid4()
    task.plan = updated_plan
    task.resume_action = "APPROVE_PLAN"
    task.resume_payload = {
        "action": "APPROVE_PLAN",
        "plan_version": task.plan_version,
        "plan": updated_plan,
        "feedback": payload.feedback,
        "decision_id": str(decision_id),
    }
    workflow_run.last_decision_id = decision_id

    task.plan_approved = True
    if payload.feedback:
        task.plan_feedback = payload.feedback

    task.status = "QUEUED"
    task.current_step = None
    task.queued_at = datetime.now(timezone.utc)
    task.worker_lease_until = None

    # Tái kích hoạt outbox để worker tiếp tục chạy
    outbox_res = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task.id,
            TaskDispatchOutbox.event_type == "START_RESEARCH",
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
    await db.refresh(task)
    return task


@router.post("/{task_id}/plan/reject", response_model=ResearchTaskResponse)
async def reject_research_plan(
    task_id: uuid.UUID,
    payload: PlanRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Người dùng từ chối kế hoạch và yêu cầu Supervisor lập kế hoạch lại với góp ý mới."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail=f"Kế hoạch chỉ có thể từ chối khi task ở trạng thái WAITING_APPROVAL (hiện tại: {task.status})",
        )
    if payload.plan_version != task.plan_version:
        raise HTTPException(status_code=409, detail="This rejection refers to an outdated plan version. Reload the current plan.")
    workflow_run = await _require_active_workflow_run(db, task, "WAITING_APPROVAL")

    task.plan_approved = False
    task.plan = None
    if payload.reason:
        task.plan_feedback = payload.reason
    decision_id = uuid.uuid4()
    task.resume_action = "REVISE_PLAN"
    task.resume_payload = {
        "action": "REVISE_PLAN",
        "plan_version": task.plan_version,
        "feedback": payload.reason or "",
        "decision_id": str(decision_id),
    }
    workflow_run.last_decision_id = decision_id

    task.status = "QUEUED"
    task.current_step = None
    task.queued_at = datetime.now(timezone.utc)
    task.worker_lease_until = None

    # Tái kích hoạt outbox
    outbox_res = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task.id,
            TaskDispatchOutbox.event_type == "START_RESEARCH",
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
    await db.refresh(task)
    return task


@router.get("/{task_id}/protocol", response_model=ProtocolResponse)
async def get_task_protocol(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem đề cương nghiên cứu khoa học (Study Protocol) của task."""
    result = await db.execute(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    content_md = None
    download_url = None
    if task.protocol_artifact_id:
        art = await db.scalar(
            select(ExportArtifact).where(
                ExportArtifact.id == task.protocol_artifact_id,
                ExportArtifact.research_task_id == task.id,
            )
        )
        if art:
            download_url = art.download_url
            file_p = artifact_store.get_artifact_path(task.id, art.file_path)
            if file_p and file_p.is_file():
                try:
                    content_md = file_p.read_text(encoding="utf-8")
                except Exception:
                    pass

    return ProtocolResponse(
        task_id=task.id,
        research_type=task.research_type,
        status=task.status,
        protocol_artifact_id=task.protocol_artifact_id,
        download_url=download_url,
        content_markdown=content_md,
    )


@router.post("/{task_id}/data/files", response_model=FieldworkUploadResponse, status_code=201)
async def upload_fieldwork_result(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store a validated result file; uploading alone does not resume research."""
    task = await db.scalar(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.research_type != "EMPIRICAL_HUMAN" or task.status != "WAITING_USER_DATA":
        raise HTTPException(status_code=409, detail="Chỉ nạp kết quả cho bài thực địa đang chờ dữ liệu.")
    count = await db.scalar(select(func.count()).select_from(ExportArtifact).where(
        ExportArtifact.research_task_id == task_id,
        ExportArtifact.export_type.in_(list(RESULT_TYPES.values())),
    ))
    if count >= settings.MAX_UPLOAD_FILES_PER_TASK:
        raise HTTPException(status_code=409, detail="Đã đạt giới hạn số tệp kết quả của bài này.")
    try:
        content = await read_upload_with_limit(file, MAX_RESULT_BYTES)
    except UploadSizeLimitExceeded:
        raise HTTPException(status_code=413, detail="Tệp kết quả vượt quá 5 MiB.")
    filename = file.filename or "results.txt"
    try:
        validated = validate_fieldwork_result(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    saved = artifact_store.save_artifact(task_id, filename, content)
    try:
        artifact = ExportArtifact(
            research_task_id=task_id,
            export_type=validated["export_type"],
            file_path=saved["file_path"],
            file_size_bytes=saved["file_size_bytes"],
        )
        db.add(artifact)
        await db.flush()
        artifact.download_url = f"/api/v1/research/{task_id}/artifacts/{artifact.id}/download"
        await db.commit()
    except Exception:
        await db.rollback()
        artifact_store.delete_artifact(task_id, saved["file_path"])
        raise
    return FieldworkUploadResponse(
        artifact_id=artifact.id, file_name=saved["file_name"],
        file_size_bytes=saved["file_size_bytes"], sha256_hash=validated["sha256_hash"],
    )


@router.post("/{task_id}/data/resume", response_model=ResearchTaskResponse)
async def resume_research_with_data(
    task_id: uuid.UUID,
    payload: UserDataResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nạp kết quả thực nghiệm/khảo sát thực tế và tiếp tục workflow (Gate G4)."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.status != "WAITING_USER_DATA":
        raise HTTPException(
            status_code=409,
            detail=f"Chỉ có thể nạp dữ liệu khi task ở trạng thái WAITING_USER_DATA (hiện tại: {task.status})",
        )

    if task.research_type != "EMPIRICAL_HUMAN":
        raise HTTPException(status_code=409, detail="Luồng này chỉ nhận kết quả nghiên cứu thực địa.")
    if payload.plan_version != task.plan_version:
        raise HTTPException(status_code=409, detail="This result belongs to an outdated plan version. Reload the current protocol.")
    workflow_run = await _require_active_workflow_run(db, task, "WAITING_USER_DATA")
    artifact = await db.scalar(select(ExportArtifact).where(
        ExportArtifact.id == payload.file_artifact_id,
        ExportArtifact.research_task_id == task.id,
        ExportArtifact.export_type.in_(list(RESULT_TYPES.values())),
    ))
    if not artifact:
        raise HTTPException(status_code=422, detail="Chọn tệp kết quả đã tải lên đúng bài nghiên cứu này.")
    try:
        file_path = artifact_store.get_artifact_path(task.id, artifact.file_path)
        if file_path is None:
            raise ValueError("Tệp kết quả không còn trong kho lưu trữ. Vui lòng tải lại.")
        with file_path.open("rb") as result_file:
            content = result_file.read(MAX_RESULT_BYTES + 1)
        if len(content) != artifact.file_size_bytes:
            raise ValueError("Tệp kết quả không còn khớp thông tin đã lưu. Vui lòng tải lại.")
        evidence = validate_fieldwork_result(file_path.name, content)
        if evidence["export_type"] != artifact.export_type:
            raise ValueError("Loại tệp kết quả không khớp thông tin đã lưu.")
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Tệp kết quả chưa sẵn sàng hoặc không hợp lệ.") from exc

    # Lưu thông tin dữ liệu thực địa
    task.user_data_submission = {
        **payload.model_dump(mode="json"),
        "artifact_evidence": {**evidence, "file_name": file_path.name},
    }
    decision_id = uuid.uuid4()
    task.resume_action = "SUBMIT_USER_DATA"
    task.resume_payload = {
        "action": "SUBMIT_USER_DATA",
        "plan_version": task.plan_version,
        "submission": task.user_data_submission,
        "decision_id": str(decision_id),
    }
    workflow_run.last_decision_id = decision_id
    task.status = "QUEUED"
    task.current_step = None
    task.queued_at = datetime.now(timezone.utc)
    task.worker_lease_until = None

    # Tái kích hoạt outbox dispatch
    outbox_res = await db.execute(
        select(TaskDispatchOutbox).where(
            TaskDispatchOutbox.research_task_id == task.id,
            TaskDispatchOutbox.event_type == "START_RESEARCH",
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
    await db.refresh(task)
    return task


@router.get("/{task_id}/experiments", response_model=List[AnalysisRunResponse])
async def get_task_experiments(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các lần chạy thực nghiệm tính toán (AnalysisRun) của task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.research_task_id == task_id)
        .order_by(AnalysisRun.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{task_id}/journal", response_model=List[ExperimentJournalEntryResponse])
async def get_task_experiment_journal(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy toàn bộ các mục nhật ký thí nghiệm (ExperimentJournalEntry, append-only) của task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(ExperimentJournalEntry)
        .where(ExperimentJournalEntry.research_task_id == task_id)
        .order_by(ExperimentJournalEntry.created_at.asc(), ExperimentJournalEntry.sequence.asc())
    )
    return result.scalars().all()


@router.post("/{task_id}/dataset", response_model=DatasetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_task_dataset(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tải lên tập dữ liệu định dạng CSV cho bài nghiên cứu thực nghiệm tính toán (EMPIRICAL_COMPUTATIONAL)."""
    task = await db.scalar(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING")
        .with_for_update()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.research_type != "EMPIRICAL_COMPUTATIONAL":
        raise HTTPException(status_code=409, detail="CSV dataset chỉ dùng cho nghiên cứu thực nghiệm tính toán")
    if task.status not in {"PENDING", "WAITING_APPROVAL", "WAITING_USER_DATA"}:
        raise HTTPException(
            status_code=409,
            detail=f"Không thể thay dataset khi task ở trạng thái {task.status}",
        )
    workflow_run = None
    if task.status == "WAITING_USER_DATA":
        workflow_run = await _require_active_workflow_run(db, task, "WAITING_USER_DATA")

    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .csv")

    try:
        content = await read_upload_with_limit(file, MAX_DATASET_BYTES)
    except UploadSizeLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Tệp CSV vượt quá giới hạn 5 MiB của phân tích thực nghiệm.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Tệp CSV trống (0 bytes)")

    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Không thể giải mã nội dung văn bản tệp CSV (hỗ trợ UTF-8)")

    try:
        headers, rows = parse_csv_dataset(csv_text)
    except InvalidInputError as err:
        raise HTTPException(status_code=400, detail=f"Dữ liệu CSV không hợp lệ: {str(err)}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Lỗi phân tích tệp CSV: {str(exc)}")

    saved = artifact_store.save_artifact(task.id, filename, content)
    art = ExportArtifact(
        research_task_id=task.id,
        export_type="DATASET_CSV",
        file_path=saved["file_path"],
        file_size_bytes=saved["file_size_bytes"],
        download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
    )
    db.add(art)
    await db.flush()
    art.download_url = f"/api/v1/research/{task.id}/artifacts/{art.id}/download"

    # Uploading the required dataset resumes a computational study that paused
    # at WAITING_USER_DATA. Reuse the durable outbox row to avoid losing the
    # resume event if the broker is temporarily unavailable.
    if task.status == "WAITING_USER_DATA":
        decision_id = uuid.uuid4()
        task.resume_action = "SUBMIT_USER_DATA"
        task.resume_payload = {
            "action": "SUBMIT_USER_DATA",
            "plan_version": task.plan_version,
            "submission": {"dataset_artifact_id": str(art.id)},
            "decision_id": str(decision_id),
        }
        workflow_run.last_decision_id = decision_id
        task.status = "QUEUED"
        task.current_step = None
        task.queued_at = datetime.now(timezone.utc)
        task.worker_lease_until = None
        outbox_res = await db.execute(
            select(TaskDispatchOutbox)
            .where(
                TaskDispatchOutbox.research_task_id == task.id,
                TaskDispatchOutbox.event_type == "START_RESEARCH",
            )
            .with_for_update()
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

    return DatasetUploadResponse(
        artifact_id=art.id,
        file_name=saved["file_name"],
        rows_count=len(rows),
        columns_count=len(headers),
        columns=headers,
        checksum=saved["sha256_hash"],
    )

