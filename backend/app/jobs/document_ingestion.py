"""Idempotent PDF ingestion with lease and ownership checks."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.models.source import ResearchSource
from app.models.report import ExportArtifact
from app.services.pdf_parser import extract_text_from_pdf
from app.tools.embedder import EmbedderTool

logger = logging.getLogger(__name__)

async def ingest_document(source_id: str, *, artifact_store) -> dict:
    """Parse and chunk one private uploaded PDF with a durable, idempotent claim."""
    source_uuid = uuid.UUID(source_id)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(
                select(ResearchTask)
                .where(ResearchTask.id == select(ResearchSource.research_task_id).where(ResearchSource.id == source_uuid).scalar_subquery())
                .with_for_update()
            )
            if task is None or task.status == "DELETING":
                return {"status": "DELETED", "source_id": source_id}
            source = await session.scalar(
                select(ResearchSource).where(ResearchSource.id == source_uuid).with_for_update()
            )
            if source is None:
                return {"status": "DELETED", "source_id": source_id}
            if source.ingestion_status == "READY":
                return {"status": "ALREADY_READY", "source_id": source_id}
            if source.ingestion_status == "PROCESSING" and source.ingestion_lease_until and source.ingestion_lease_until > now:
                return {"status": "ALREADY_PROCESSING", "source_id": source_id}
            source.ingestion_status = "PROCESSING"
            source.ingestion_error = None
            source.ingestion_attempt += 1
            attempt = source.ingestion_attempt
            source.ingestion_lease_until = now + timedelta(seconds=settings.WORKER_LEASE_SECONDS)
            task_id = source.research_task_id
            artifact_id = source.upload_artifact_id

    try:
        async with AsyncSessionLocal() as session:
            artifact = await session.scalar(
                select(ExportArtifact).where(
                    ExportArtifact.id == artifact_id,
                    ExportArtifact.research_task_id == task_id,
                    ExportArtifact.export_type == "PDF_UPLOAD",
                )
            )
            if artifact is None:
                raise FileNotFoundError("Uploaded document artifact is unavailable")
            path = artifact_store.get_artifact_path(task_id, artifact.file_path)
            if path is None:
                raise FileNotFoundError("Uploaded document file is unavailable")
            content = await asyncio.to_thread(path.read_bytes)
            if len(content) != artifact.file_size_bytes:
                raise ValueError("Uploaded document size does not match its stored metadata")
            import hashlib
            checksum = hashlib.sha256(content).hexdigest()
            source = await session.get(ResearchSource, source_uuid)
            if source is None or checksum != source.content_checksum:
                raise ValueError("Uploaded document checksum validation failed")

        parsed = await asyncio.to_thread(extract_text_from_pdf, content)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await session.scalar(
                    select(ResearchTask).where(ResearchTask.id == task_id).with_for_update()
                )
                if task is None or task.status == "DELETING":
                    return {"status": "DELETED", "source_id": source_id}
                source = await session.scalar(
                    select(ResearchSource).where(ResearchSource.id == source_uuid).with_for_update()
                )
                if source is None:
                    return {"status": "DELETED", "source_id": source_id}
                if source.ingestion_attempt != attempt or source.ingestion_status != "PROCESSING":
                    return {"status": "SUPERSEDED", "source_id": source_id}
                source.title = parsed.get("title") or source.title
                source.author = parsed.get("author")
                source.content_snippet = parsed["text"][:500]
                source.summary = (
                    f"PDF ({parsed['page_count']} pages, {len(content)} bytes). "
                    f"SHA256: {checksum}"
                )
                chunk_count = await EmbedderTool().embed_and_store(
                    db=session,
                    task_id=task_id,
                    source_id=source_uuid,
                    text_content=parsed["text"],
                )
                source.ingestion_status = "READY"
                source.ingestion_error = None
                source.ingestion_lease_until = None
        logger.info(
            "PDF ingestion ready task=%s source=%s attempt=%s pages=%s chunks=%s",
            task_id, source_uuid, attempt, parsed["page_count"], chunk_count,
        )
        return {
            "status": "READY",
            "task_id": str(task_id),
            "source_id": source_id,
            "page_count": parsed["page_count"],
            "chunks_count": chunk_count,
        }
    except Exception as exc:
        safe_error = f"{type(exc).__name__}: {str(exc)[:400]}"
        async with AsyncSessionLocal() as session:
            async with session.begin():
                source = await session.scalar(
                    select(ResearchSource).where(ResearchSource.id == source_uuid).with_for_update()
                )
                if source and source.ingestion_attempt == attempt and source.ingestion_status == "PROCESSING":
                    source.ingestion_status = "FAILED"
                    source.ingestion_error = safe_error
                    source.ingestion_lease_until = None
        logger.exception("PDF ingestion failed task=%s source=%s attempt=%s", task_id, source_uuid, attempt)
        return {"status": "FAILED", "task_id": str(task_id), "source_id": source_id, "error": safe_error}


