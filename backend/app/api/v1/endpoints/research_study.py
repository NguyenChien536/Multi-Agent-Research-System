"""Plan approval, protocols, user data, and experiment records for a research task."""
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.task import ResearchTask, TaskDispatchOutbox, WorkflowRun
from app.models.user import User
from app.models.report import ExportArtifact
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.schemas.task import (ResearchTaskResponse, PlanReviewResponse, PlanApprovalRequest,
    PlanRejectRequest, UserDataResumeRequest, ProtocolResponse)
from app.schemas.artifact import FieldworkUploadResponse
from app.schemas.experiment import AnalysisRunResponse, ExperimentJournalEntryResponse, DatasetUploadResponse
from app.services.experiment_runner import MAX_DATASET_BYTES, parse_csv_dataset, InvalidInputError
from app.services.artifact_store import artifact_store
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
