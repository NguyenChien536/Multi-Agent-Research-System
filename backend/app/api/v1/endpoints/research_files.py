"""Private PDF uploads and research artifact downloads."""
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.task import ResearchTask, DocumentIngestionOutbox
from app.models.user import User
from app.models.report import ExportArtifact
from app.models.source import ResearchSource
from app.schemas.artifact import ArtifactItemResponse, PdfUploadResponse
from app.services.artifact_store import artifact_store
from app.services.pdf_parser import validate_pdf_bytes, PdfSizeLimitError, PdfValidationError
from app.services.upload_reader import read_upload_with_limit, UploadSizeLimitExceeded

router = APIRouter()

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
