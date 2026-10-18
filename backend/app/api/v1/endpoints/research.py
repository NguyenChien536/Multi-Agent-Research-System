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
from app.models.task import ResearchTask, TaskDispatchOutbox
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
from app.schemas.artifact import ArtifactItemResponse, PdfUploadResponse
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.schemas.experiment import (
    AnalysisRunResponse,
    ExperimentJournalEntryResponse,
    DatasetUploadResponse,
)
from app.services.experiment_runner import parse_csv_dataset, InvalidInputError
from app.services.artifact_store import artifact_store
from app.services.pdf_parser import (
    extract_text_from_pdf,
    PdfSizeLimitError,
    PdfPageLimitError,
    PdfOcrRequiredError,
    PdfValidationError,
)
from app.tools.embedder import EmbedderTool

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
    # Cleanup task artifacts on disk (SRS FR-02 & Tombstone cleanup)
    try:
        artifact_store.delete_task_artifacts(task_id)
    except Exception:
        pass
    return {"message": "Research task deleted successfully", "task_id": str(task_id)}


@router.get("/{task_id}/agent-runs", response_model=List[AgentRunItemResponse])
async def get_task_agent_runs(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy lịch sử thực thi của các Agent trong Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Research task not found")

    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.research_task_id == task_id)
        .order_by(AgentRun.started_at.asc(), AgentRun.id.asc())
    )
    return result.scalars().all()


@router.post("/{task_id}/upload", response_model=PdfUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_task_pdf(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tải lên tài liệu PDF riêng tư (Private Artifact), trích xuất văn bản và băm nhỏ thành DocumentChunk.
    """
    # 1. Kiểm tra quyền sở hữu task
    task_res = await db.execute(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    task = task_res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    if task.status in {"CANCELLED", "COMPLETED", "FAILED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể tải lên tài liệu cho bài nghiên cứu ở trạng thái {task.status}",
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
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lỗi khi đọc file tải lên: {e}")

    # 4. Phân tích cú pháp và trích xuất text
    try:
        parsed_doc = extract_text_from_pdf(content)
    except PdfSizeLimitError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except PdfOcrRequiredError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except (PdfPageLimitError, PdfValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lỗi phân tích file PDF: {e}")

    # 5. Lưu file vật lý an toàn vào ArtifactStore
    filename = file.filename or "document.pdf"
    artifact_meta = artifact_store.save_artifact(task_id=task.id, filename=filename, content=content)

    # 6. Tạo bản ghi ExportArtifact
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

    # 7. Tạo bản ghi ResearchSource
    all_sources_res = await db.execute(
        select(func.count(ResearchSource.id)).where(ResearchSource.research_task_id == task.id)
    )
    total_sources = all_sources_res.scalar_one()
    source_tag = f"src_{total_sources + 1:02d}"

    source_title = parsed_doc["title"] or filename
    db_source = ResearchSource(
        research_task_id=task.id,
        source_tag=source_tag,
        title=source_title,
        url=f"file://{artifact_meta['file_name']}",
        source_type="PDF",
        author=parsed_doc.get("author"),
        content_snippet=parsed_doc["text"][:500],
        summary=f"Tài liệu PDF tải lên ({parsed_doc['page_count']} trang, {artifact_meta['file_size_bytes']} bytes). SHA256: {artifact_meta['sha256_hash'][:16]}...",
        relevance_score=1.0,
    )
    db.add(db_source)
    await db.flush()

    # 8. Chia nhỏ (Chunking) và tạo Vector Embedding trong pgvector
    embedder = EmbedderTool()
    chunks_count = await embedder.embed_and_store(
        db=db,
        task_id=task.id,
        source_id=db_source.id,
        text_content=parsed_doc["text"],
    )

    await db.commit()

    return PdfUploadResponse(
        artifact_id=artifact.id,
        source_id=db_source.id,
        source_tag=source_tag,
        file_name=artifact_meta["file_name"],
        file_size_bytes=artifact_meta["file_size_bytes"],
        page_count=parsed_doc["page_count"],
        chunks_count=chunks_count,
        sha256_hash=artifact_meta["sha256_hash"],
        message="Tải lên và nạp dữ liệu PDF thành công",
    )


@router.get("/{task_id}/artifacts", response_model=List[ArtifactItemResponse])
async def list_task_artifacts(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các tệp tin / tài liệu riêng tư của Research Task."""
    task_res = await db.execute(
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    return PlanReviewResponse(
        task_id=task.id,
        status=task.status,
        require_plan_approval=task.require_plan_approval,
        plan_approved=task.plan_approved,
        plan=task.plan,
        plan_feedback=task.plan_feedback,
    )


@router.post("/{task_id}/plan/approve", response_model=ResearchTaskResponse)
async def approve_research_plan(
    task_id: uuid.UUID,
    payload: PlanApprovalRequest = Body(default_factory=PlanApprovalRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Người dùng duyệt kế hoạch nghiên cứu và tiếp tục workflow."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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

    # Nếu người dùng có chỉnh sửa search queries
    if payload.approved_queries and task.plan:
        updated_plan = dict(task.plan)
        updated_plan["search_queries"] = payload.approved_queries
        task.plan = updated_plan

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
    else:
        db.add(TaskDispatchOutbox(research_task_id=task.id, event_type="START_RESEARCH"))

    await db.commit()
    await db.refresh(task)
    return task


@router.post("/{task_id}/plan/reject", response_model=ResearchTaskResponse)
async def reject_research_plan(
    task_id: uuid.UUID,
    payload: PlanRejectRequest = Body(default_factory=PlanRejectRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Người dùng từ chối kế hoạch và yêu cầu Supervisor lập kế hoạch lại với góp ý mới."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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

    task.plan_approved = False
    task.plan = None
    if payload.reason:
        task.plan_feedback = payload.reason

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
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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
        .where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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

    # Lưu thông tin dữ liệu thực địa
    task.user_data_submission = payload.model_dump()
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
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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
        select(ResearchTask.id).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
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
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == current_user.id)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .csv")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Tệp CSV trống (0 bytes)")
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="Dung lượng tệp vượt quá giới hạn cho phép (tối đa 10MB)")

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
    await db.commit()

    return DatasetUploadResponse(
        artifact_id=art.id,
        file_name=saved["file_name"],
        rows_count=len(rows),
        columns_count=len(headers),
        columns=headers,
        checksum=saved["sha256_hash"],
    )

