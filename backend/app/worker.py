import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import func, select, update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.source import DocumentChunk, ResearchSource
from app.models.report import ExportArtifact, ResearchReport
from app.models.grounding import Citation, ClaimEvidence, Evidence, ResearchClaim
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.user import User
from app.agents.graph import research_graph
from app.agents.state import ResearchState
from app.services.artifact_store import artifact_store
import json

logger = logging.getLogger(__name__)

# Khởi tạo Celery Application
celery_app = Celery(
    "research_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Cấu hình Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Idempotency & Worker Crash Protection
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 360},
    worker_prefetch_multiplier=1,  # Đảm bảo phân bổ task công bằng
)


async def renew_worker_lease(task_id: str, attempt_number: int) -> None:
    """Renew the active claim so the API dispatcher can recover dead workers."""
    while True:
        await asyncio.sleep(settings.WORKER_HEARTBEAT_SECONDS)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(ResearchTask)
                .where(
                    ResearchTask.id == task_id,
                    ResearchTask.status == "RUNNING",
                    ResearchTask.attempt_number == attempt_number,
                )
                .values(worker_lease_until=datetime.now(timezone.utc) + timedelta(seconds=settings.WORKER_LEASE_SECONDS))
            )
            await session.commit()
            if result.rowcount != 1:
                return


async def run_langgraph_workflow(task_id: str) -> dict:
    """Hàm chạy async LangGraph và tương tác với DB."""
    heartbeat: asyncio.Task | None = None
    try:
        async with AsyncSessionLocal() as session:
            # Claim only a queued task. A duplicate Celery delivery is acknowledged
            # without starting another graph run or creating another report.
            result = await session.execute(
                select(ResearchTask)
                .where(ResearchTask.id == task_id)
                .with_for_update()
            )
            task = result.scalar_one_or_none()
            if not task:
                return {"status": "FAILED", "task_id": task_id, "message": "Task not found in DB"}
            if task.status != "QUEUED":
                return {"status": "IGNORED", "task_id": task_id, "message": f"Task is {task.status}"}

            # Atomically serialize capacity checks for this user across concurrent workers.
            if task.user_id:
                await session.execute(
                    select(User.id)
                    .where(User.id == task.user_id)
                    .with_for_update()
                )

            # Enforce the per-user running job limit.
            # Queued and WAITING_* states do not consume running slots.
            active_count_res = await session.execute(
                select(func.count(ResearchTask.id))
                .where(
                    ResearchTask.user_id == task.user_id,
                    ResearchTask.status == "RUNNING",
                )
            )
            active_count = active_count_res.scalar_one()
            if active_count >= settings.MAX_CONCURRENT_TASKS_PER_USER:
                # User has reached concurrent running job limit.
                # Task remains QUEUED; reset outbox event so it is dispatched when capacity frees.
                event_result = await session.execute(
                    select(TaskDispatchOutbox)
                    .where(
                        TaskDispatchOutbox.research_task_id == task.id,
                        TaskDispatchOutbox.event_type == "START_RESEARCH",
                    )
                    .with_for_update()
                )
                outbox_event = event_result.scalar_one_or_none()
                if outbox_event is not None:
                    outbox_event.dispatched_at = None
                    outbox_event.available_at = datetime.now(timezone.utc)
                    outbox_event.locked_until = None
                    outbox_event.unclaimed_retries = 0
                    outbox_event.last_error = "User at concurrent running job limit; waiting for capacity"
                await session.commit()
                return {
                    "status": "QUEUED",
                    "task_id": task_id,
                    "message": "User has reached concurrent running job limit; task remains QUEUED",
                }

            task.status = "RUNNING"
            task.current_step = None
            task.attempt_number += 1
            task.worker_lease_until = datetime.now(timezone.utc) + timedelta(seconds=settings.WORKER_LEASE_SECONDS)
            dispatch_result = await session.execute(
                select(TaskDispatchOutbox)
                .where(
                    TaskDispatchOutbox.research_task_id == task.id,
                    TaskDispatchOutbox.event_type == "START_RESEARCH",
                )
                .with_for_update()
            )
            dispatch_event = dispatch_result.scalar_one_or_none()
            if dispatch_event is not None:
                dispatch_event.unclaimed_retries = 0
                dispatch_event.last_error = None
            claim_attempt = task.attempt_number
            user_id = task.user_id
            await session.commit()
            heartbeat = asyncio.create_task(renew_worker_lease(task_id, claim_attempt))

            # Preload existing sources (e.g. uploaded private PDFs) into initial state
            existing_sources_res = await session.execute(
                select(ResearchSource)
                .where(ResearchSource.research_task_id == task.id)
                .order_by(ResearchSource.created_at.asc())
            )
            existing_sources = existing_sources_res.scalars().all()
            preloaded_sources = []
            visited_urls = set()
            for src in existing_sources:
                preloaded_sources.append({
                    "db_id": str(src.id),
                    "source_tag": src.source_tag,
                    "title": src.title,
                    "url": src.url,
                    "content": src.content_snippet or "",
                    "source_type": src.source_type,
                })
                visited_urls.add(src.url)

            # Preload dataset CSV if user uploaded one for empirical computational research
            preloaded_dataset_csv = None
            uploaded_dataset_art_id = None
            if getattr(task, "research_type", "REVIEW") == "EMPIRICAL_COMPUTATIONAL":
                dataset_art_res = await session.execute(
                    select(ExportArtifact)
                    .where(
                        ExportArtifact.research_task_id == task.id,
                        ExportArtifact.export_type == "DATASET_CSV",
                    )
                    .order_by(ExportArtifact.created_at.desc())
                )
                dataset_art = dataset_art_res.scalars().first()
                if dataset_art and dataset_art.file_path:
                    uploaded_dataset_art_id = dataset_art.id
                    art_file_path = artifact_store.get_artifact_path(task.id, dataset_art.file_path)
                    if art_file_path and art_file_path.is_file():
                        try:
                            dataset_bytes = art_file_path.read_bytes()
                            try:
                                preloaded_dataset_csv = dataset_bytes.decode("utf-8-sig")
                            except UnicodeDecodeError:
                                # Match the upload validator's legacy Latin-1 fallback.
                                preloaded_dataset_csv = dataset_bytes.decode("latin-1")
                        except Exception as e:
                            logger.warning("Could not read uploaded dataset artifact for task %s: %s", task_id, e)

            # 2. Khởi tạo State ban đầu
            initial_state = {
                "task_id": str(task.id),
                "user_id": str(task.user_id) if task.user_id else "anonymous",
                "research_question": task.research_question,
                "research_depth": task.research_depth,
                "research_type": getattr(task, "research_type", "REVIEW") or "REVIEW",
                "language": task.language,
                "status": "RUNNING",
                "require_plan_approval": task.require_plan_approval,
                "plan_approved": task.plan_approved,
                "plan": task.plan or {},
                "plan_feedback": task.plan_feedback,
                "protocol_artifact_id": str(task.protocol_artifact_id) if task.protocol_artifact_id else None,
                "user_data_submission": task.user_data_submission or None,
                "dataset_csv": preloaded_dataset_csv,
                "dataset_artifact_id": str(uploaded_dataset_art_id) if uploaded_dataset_art_id else None,
                "current_iteration": task.current_iteration,
                "current_micro_revision": 0,
                "max_iterations": task.max_iterations,
                "max_micro_revisions": 2,
                "attempt_number": task.attempt_number,
                "collected_sources": preloaded_sources,
                "visited_urls": visited_urls,
            }

            # 3. Kích hoạt (Invoke) Graph
            try:
                final_state = await research_graph.ainvoke(initial_state)

                # Kiểm tra nếu graph dừng tại điểm duyệt kế hoạch (HITL)
                if final_state and final_state.get("status") == "WAITING_APPROVAL":
                    await session.refresh(task)
                    if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                        return {"status": "SUPERSEDED", "task_id": task_id}

                    task.status = "WAITING_APPROVAL"
                    task.current_step = "Supervisor"
                    task.plan = final_state.get("plan")
                    task.plan_approved = False
                    task.worker_lease_until = None
                    await session.commit()
                    logger.info("Task %s: Paused at WAITING_APPROVAL. Worker lease released.", task_id)
                    return {"status": "WAITING_APPROVAL", "task_id": task_id}

                # Kiểm tra nếu graph dừng tại điểm chờ dữ liệu thực địa của người dùng (Gate G4)
                if final_state and final_state.get("status") == "WAITING_USER_DATA":
                    await session.refresh(task)
                    if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                        return {"status": "SUPERSEDED", "task_id": task_id}

                    task.status = "WAITING_USER_DATA"
                    task.current_step = (
                        "Waiting for dataset"
                        if getattr(task, "research_type", "REVIEW") == "EMPIRICAL_COMPUTATIONAL"
                        else "Methodologist"
                    )

                    proto_info = final_state.get("protocol") or {}
                    markdown_content = proto_info.get("protocol_markdown") or ""
                    if markdown_content and not task.protocol_artifact_id:
                        saved_file = artifact_store.save_artifact(
                            task_id=task.id,
                            filename="study_protocol.md",
                            content=markdown_content.encode("utf-8"),
                        )
                        art = ExportArtifact(
                            research_task_id=task.id,
                            export_type="PROTOCOL",
                            file_path=saved_file["file_path"],
                            file_size_bytes=saved_file["file_size_bytes"],
                            download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                        )
                        session.add(art)
                        await session.flush()
                        art.download_url = f"/api/v1/research/{task.id}/artifacts/{art.id}/download"
                        task.protocol_artifact_id = art.id

                    task.worker_lease_until = None
                    await session.commit()
                    logger.info("Task %s: Paused at WAITING_USER_DATA. Worker lease released.", task_id)
                    return {"status": "WAITING_USER_DATA", "task_id": task_id}

                report_content = final_state.get("final_report_markdown") if final_state else None
                if not report_content:
                    raise RuntimeError("Research graph completed without producing a report")

                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}

                report = ResearchReport(
                    research_task_id=task.id,
                    title=f"Báo cáo: {task.title}",
                    content_markdown=report_content,
                    word_count=len(report_content.split()),
                )
                session.add(report)
                await session.flush()

                # Citation rows are created only from persisted, verified
                # claim/evidence links owned by this task. This keeps report
                # references traceable and rejects graph-state tampering.
                for number, item in enumerate(final_state.get("citations", []), start=1):
                    try:
                        claim_id = uuid.UUID(str(item["claim_id"]))
                        evidence_id = uuid.UUID(str(item["evidence_id"]))
                        source_id = uuid.UUID(str(item["source_id"]))
                        chunk_id = uuid.UUID(str(item["chunk_id"]))
                    except (KeyError, TypeError, ValueError):
                        logger.warning("Skipping malformed citation metadata for task %s", task_id)
                        continue

                    lineage = await session.execute(
                        select(ResearchClaim.id, ResearchClaim.claim_text)
                        .join(ClaimEvidence, ClaimEvidence.claim_id == ResearchClaim.id)
                        .join(Evidence, Evidence.id == ClaimEvidence.evidence_id)
                        .join(DocumentChunk, DocumentChunk.id == Evidence.chunk_id)
                        .join(ResearchSource, ResearchSource.id == DocumentChunk.source_id)
                        .where(
                            ResearchClaim.id == claim_id,
                            ResearchClaim.research_task_id == task.id,
                            ResearchClaim.is_verified.is_(True),
                            Evidence.id == evidence_id,
                            Evidence.research_task_id == task.id,
                            Evidence.source_id == source_id,
                            Evidence.chunk_id == chunk_id,
                            DocumentChunk.research_task_id == task.id,
                            DocumentChunk.source_id == source_id,
                            ResearchSource.id == source_id,
                            ResearchSource.research_task_id == task.id,
                        )
                    )
                    lineage_row = lineage.one_or_none()
                    if lineage_row is None:
                        logger.warning("Skipping unverified/cross-task citation for task %s", task_id)
                        continue

                    session.add(Citation(
                        research_task_id=task.id,
                        report_id=report.id,
                        source_id=source_id,
                        chunk_id=chunk_id,
                        claim_id=claim_id,
                        citation_number=number,
                        citation_label=f"[{number}]",
                        claim_text=lineage_row.claim_text,
                    ))

                # Persist AnalysisRun, ExperimentJournalEntry, and experiment artifacts if routine ran
                analysis_data = final_state.get("analysis_run")
                if analysis_data:
                    metrics_bytes = json.dumps(analysis_data.get("metrics", {}), indent=2).encode("utf-8")
                    manifest_bytes = json.dumps(analysis_data.get("manifest", {}), indent=2).encode("utf-8")
                    chart_bytes = json.dumps(analysis_data.get("chart_data", {}), indent=2).encode("utf-8")
                    readme_bytes = (analysis_data.get("readme_markdown") or "").encode("utf-8")

                    saved_metrics = artifact_store.save_artifact(task.id, "metrics.json", metrics_bytes)
                    art_metrics = ExportArtifact(
                        research_task_id=task.id,
                        export_type="METRICS_JSON",
                        file_path=saved_metrics["file_path"],
                        file_size_bytes=saved_metrics["file_size_bytes"],
                        download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                    )
                    session.add(art_metrics)

                    saved_manifest = artifact_store.save_artifact(task.id, "manifest.json", manifest_bytes)
                    art_manifest = ExportArtifact(
                        research_task_id=task.id,
                        export_type="MANIFEST_JSON",
                        file_path=saved_manifest["file_path"],
                        file_size_bytes=saved_manifest["file_size_bytes"],
                        download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                    )
                    session.add(art_manifest)

                    saved_chart = artifact_store.save_artifact(task.id, "chart_data.json", chart_bytes)
                    art_chart = ExportArtifact(
                        research_task_id=task.id,
                        export_type="CHART_DATA_JSON",
                        file_path=saved_chart["file_path"],
                        file_size_bytes=saved_chart["file_size_bytes"],
                        download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                    )
                    session.add(art_chart)

                    saved_readme = artifact_store.save_artifact(task.id, "reproducibility_readme.md", readme_bytes)
                    art_readme = ExportArtifact(
                        research_task_id=task.id,
                        export_type="REPRO_README",
                        file_path=saved_readme["file_path"],
                        file_size_bytes=saved_readme["file_size_bytes"],
                        download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                    )
                    session.add(art_readme)
                    await session.flush()

                    art_metrics.download_url = f"/api/v1/research/{task.id}/artifacts/{art_metrics.id}/download"
                    art_manifest.download_url = f"/api/v1/research/{task.id}/artifacts/{art_manifest.id}/download"
                    art_chart.download_url = f"/api/v1/research/{task.id}/artifacts/{art_chart.id}/download"
                    art_readme.download_url = f"/api/v1/research/{task.id}/artifacts/{art_readme.id}/download"

                    dataset_artifact_id = uploaded_dataset_art_id
                    if not dataset_artifact_id and final_state.get("dataset_csv"):
                        saved_ds = artifact_store.save_artifact(
                            task.id, "benchmark_dataset.csv", final_state["dataset_csv"].encode("utf-8")
                        )
                        art_ds = ExportArtifact(
                            research_task_id=task.id,
                            export_type="DATASET_CSV",
                            file_path=saved_ds["file_path"],
                            file_size_bytes=saved_ds["file_size_bytes"],
                            download_url=f"/api/v1/research/{task.id}/artifacts/placeholder/download",
                        )
                        session.add(art_ds)
                        await session.flush()
                        art_ds.download_url = f"/api/v1/research/{task.id}/artifacts/{art_ds.id}/download"
                        dataset_artifact_id = art_ds.id

                    run_record = AnalysisRun(
                        research_task_id=task.id,
                        routine_name=analysis_data.get("routine_name", "tabular_regression_v1"),
                        status=analysis_data.get("status", "COMPLETED"),
                        dataset_artifact_id=dataset_artifact_id,
                        input_checksum=analysis_data.get("input_checksum"),
                        manifest=analysis_data.get("manifest", {}),
                        metrics=analysis_data.get("metrics"),
                        reproducibility_status=analysis_data.get("reproducibility_status", "NOT_RUN"),
                        reproducibility_diff=analysis_data.get("reproducibility_diff"),
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(run_record)
                    await session.flush()

                    journal_art_ids = [str(art_metrics.id), str(art_manifest.id), str(art_chart.id), str(art_readme.id)]
                    for entry in final_state.get("experiment_journal", []):
                        j_entry = ExperimentJournalEntry(
                            research_task_id=task.id,
                            analysis_run_id=run_record.id,
                            sequence=entry["sequence"],
                            kind=entry["kind"],
                            actor=entry["actor"],
                            payload=entry.get("payload", {}),
                            artifact_ids=journal_art_ids,
                        )
                        session.add(j_entry)

                from app.models.agent_run import AgentRun
                totals_res = await session.execute(
                    select(
                        func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0),
                        func.coalesce(func.sum(AgentRun.estimated_cost), 0.0),
                    ).where(AgentRun.research_task_id == task.id)
                )
                total_tokens, total_cost = totals_res.one()

                task.total_tokens_used = int(total_tokens)
                task.total_cost_usd = round(float(total_cost), 4)
                task.completed_at = datetime.now(timezone.utc)
                task.status = "COMPLETED"
                task.worker_lease_until = None
                await session.commit()

                try:
                    from app.services.task_dispatcher import dispatch_one_outbox_event
                    await dispatch_one_outbox_event(user_id=user_id)
                except Exception as dispatch_err:
                    logger.warning("Failed to dispatch next queued task after completion: %s", dispatch_err)

                return {
                    "status": "SUCCESS",
                    "task_id": task_id,
                    "message": "Workflow completed",
                    "final_agent": final_state.get("current_agent")
                }
            except Exception as e:
                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}
                task.status = "FAILED"
                task.completed_at = datetime.now(timezone.utc)
                task.worker_lease_until = None
                # Detailed provider/runtime exceptions stay in server logs;
                # do not expose arbitrary exception text through task.description.
                error_msg = f"ERROR: Research workflow failed ({type(e).__name__})."
                task.description = f"{task.description}\n\n{error_msg}" if task.description else error_msg

                from app.models.agent_run import AgentRun
                totals_res = await session.execute(
                    select(
                        func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0),
                        func.coalesce(func.sum(AgentRun.estimated_cost), 0.0),
                    ).where(AgentRun.research_task_id == task.id)
                )
                total_tokens, total_cost = totals_res.one()
                task.total_tokens_used = int(total_tokens)
                task.total_cost_usd = round(float(total_cost), 4)
                await session.commit()

                try:
                    from app.services.task_dispatcher import dispatch_one_outbox_event
                    await dispatch_one_outbox_event(user_id=user_id)
                except Exception as dispatch_err:
                    logger.warning("Failed to dispatch next queued task after failure: %s", dispatch_err)

                raise RuntimeError(f"Research workflow failed for task {task_id}: {e}") from e
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass


@celery_app.task(bind=True, name="app.worker.execute_research_workflow")
def execute_research_workflow(self, task_id: str):
    """Task nền thực thi toàn bộ luồng Multi-Agent LangGraph cho một research task."""
    self.update_state(state="PROGRESS", meta={"message": "Khởi tạo LangGraph Engine"})

    # Celery chạy hàm đồng bộ, gọi hàm bất đồng bộ bằng asyncio.run
    result = asyncio.run(run_langgraph_workflow(task_id))

    return result
