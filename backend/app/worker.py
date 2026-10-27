import asyncio
from contextlib import asynccontextmanager
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import func, select, update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.worker_runtime import run_worker_coroutine
from app.models.task import ResearchTask, TaskDispatchOutbox, DocumentIngestionOutbox, TaskDeletionOutbox, WorkflowRun
from app.models.source import DocumentChunk, ResearchSource
from app.models.report import ExportArtifact, ResearchReport, ReportVersion
from app.models.grounding import Citation, ClaimEvidence, Evidence, ResearchClaim
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.user import User
from app.agents.graph import research_graph, build_research_graph
from app.agents.state import ResearchState
from app.services.artifact_store import artifact_store
from app.services.pdf_parser import extract_text_from_pdf
from app.tools.embedder import EmbedderTool
import json

logger = logging.getLogger(__name__)

_DEFAULT_RESEARCH_GRAPH = research_graph
_CHECKPOINT_SCHEMA_READY = False


async def _ensure_checkpoint_schema() -> None:
    """Initialize LangGraph's checkpoint schema before opening the task transaction."""
    global _CHECKPOINT_SCHEMA_READY
    if _CHECKPOINT_SCHEMA_READY or research_graph is not _DEFAULT_RESEARCH_GRAPH:
        return

    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as checkpointer:
        await checkpointer.conn.execute("SET lock_timeout = '30s'")
        await checkpointer.conn.execute("SELECT pg_advisory_lock(736421905)")
        try:
            await checkpointer.setup()
        finally:
            await checkpointer.conn.execute("SELECT pg_advisory_unlock(736421905)")
    _CHECKPOINT_SCHEMA_READY = True


@asynccontextmanager
async def _graph_for_worker():
    """Use PostgreSQL checkpoints in production and preserve graph test doubles."""
    if research_graph is not _DEFAULT_RESEARCH_GRAPH:
        yield research_graph
        return

    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as checkpointer:
        yield build_research_graph(checkpointer=checkpointer)


async def _invoke_checkpointed_graph(graph, initial_state, task, run: WorkflowRun, preloaded_dataset_csv):
    from langgraph.types import Command

    config = {"configurable": {"thread_id": run.checkpoint_thread_id}}
    if not hasattr(graph, "aget_state") or getattr(graph, "checkpointer", None) is None:
        return await graph.ainvoke(initial_state), config

    snapshot = await graph.aget_state(config)
    if snapshot and getattr(snapshot, "values", None):
        pending_interrupts = [
            item.value
            for pending_task in getattr(snapshot, "tasks", ())
            for item in getattr(pending_task, "interrupts", ())
        ]
        if pending_interrupts:
            interrupt_value = pending_interrupts[0]
            expected_actions = {
                "PLAN_APPROVAL": {"APPROVE_PLAN", "REVISE_PLAN"},
                "USER_DATA": {"SUBMIT_USER_DATA"},
            }
            action = task.resume_action
            if not action or action not in expected_actions.get(interrupt_value.get("kind"), set()):
                raise RuntimeError("This workflow is paused; a matching versioned user decision is required")
            resume_payload = task.resume_payload or {}
            if resume_payload.get("plan_version") != interrupt_value.get("plan_version"):
                raise RuntimeError("Saved user decision does not match the checkpoint plan version")
            checkpoint_update = {key: initial_state[key] for key in (
                "attempt_number", "report_length", "citation_style", "max_sources", "enforce_provider_budget"
            ) if key in initial_state}
            if preloaded_dataset_csv is not None:
                checkpoint_update["dataset_csv"] = preloaded_dataset_csv
                checkpoint_update["dataset_artifact_id"] = initial_state.get("dataset_artifact_id")
            return await graph.ainvoke(
                Command(
                    resume=resume_payload,
                    update=checkpoint_update,
                ),
                config=config,
            ), config

        if not getattr(snapshot, "next", ()) and snapshot.values.get("final_report_markdown"):
            return snapshot.values, config

        # The checkpoint advanced before a worker crash but the task row still
        # carries the submitted decision. Resume from graph state, never replay it.
        return await graph.ainvoke(
            Command(update={key: initial_state[key] for key in (
                "attempt_number", "report_length", "citation_style", "max_sources", "enforce_provider_budget"
            ) if key in initial_state}), config=config
        ), config

    return await graph.ainvoke(initial_state, config=config), config

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
    claim_attempt: int | None = None
    workflow_run_id: uuid.UUID | None = None
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
            active_run_res = await session.execute(
                select(WorkflowRun)
                .where(
                    WorkflowRun.research_task_id == task.id,
                    WorkflowRun.status.in_(["RUNNING", "WAITING_APPROVAL", "WAITING_USER_DATA"]),
                )
                .order_by(WorkflowRun.run_number.desc())
                .limit(1)
                .with_for_update()
            )
            workflow_run = active_run_res.scalar_one_or_none()
            if workflow_run is None:
                last_run_number = await session.scalar(
                    select(func.max(WorkflowRun.run_number)).where(WorkflowRun.research_task_id == task.id)
                )
                workflow_run = WorkflowRun(
                    research_task_id=task.id,
                    run_number=(last_run_number or 0) + 1,
                    status="RUNNING",
                    checkpoint_thread_id=str(uuid.uuid4()),
                    plan_version=task.plan_version,
                )
                session.add(workflow_run)
                await session.flush()
                config = dict(task.budget_config or {})
                config["_worker_recoveries"] = 0
                task.budget_config = config
            else:
                workflow_run.status = "RUNNING"
                workflow_run.updated_at = datetime.now(timezone.utc)
                task.plan_version = max(task.plan_version, workflow_run.plan_version)
            workflow_run_id = workflow_run.id
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
            await _ensure_checkpoint_schema()
            heartbeat = asyncio.create_task(renew_worker_lease(task_id, claim_attempt))
            from app.services.provider_budget import resume_active_clock, remaining_active_seconds
            await resume_active_clock(task.id)

            # Preload existing sources (e.g. uploaded private PDFs) into initial state
            existing_sources_res = await session.execute(
                select(ResearchSource)
                .where(
                    ResearchSource.research_task_id == task.id,
                    ResearchSource.ingestion_status == "READY",
                )
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
                "report_length": task.report_length,
                "citation_style": task.citation_style,
                "max_sources": task.max_sources,
                "research_type": getattr(task, "research_type", "REVIEW") or "REVIEW",
                "language": task.language,
                "status": "RUNNING",
                "require_plan_approval": task.require_plan_approval,
                "plan_approved": task.plan_approved,
                "plan": task.plan or {},
                "plan_version": task.plan_version,
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
                "workflow_run_id": str(workflow_run_id),
                "enforce_provider_budget": True,
                "collected_sources": preloaded_sources,
                "visited_urls": visited_urls,
            }

            # 3. Kích hoạt (Invoke) Graph
            try:
                async with _graph_for_worker() as graph:
                    async with asyncio.timeout(await remaining_active_seconds(task.id)):
                        final_state, _graph_config = await _invoke_checkpointed_graph(
                            graph, initial_state, task, workflow_run, preloaded_dataset_csv
                        )

                pending_interrupts = (final_state or {}).get("__interrupt__", ())
                interrupt_info = None
                if pending_interrupts:
                    interrupt_info = getattr(pending_interrupts[0], "value", pending_interrupts[0])
                pause_kind = (interrupt_info or {}).get("kind")
                if not pause_kind and final_state:
                    if final_state.get("status") == "WAITING_APPROVAL":
                        pause_kind = "PLAN_APPROVAL"
                    elif final_state.get("status") == "WAITING_USER_DATA":
                        pause_kind = "USER_DATA"

                # Kiểm tra nếu graph dừng tại điểm duyệt kế hoạch (HITL)
                if pause_kind == "PLAN_APPROVAL":
                    from app.services.provider_budget import pause_active_clock
                    await pause_active_clock(task.id)
                    await session.refresh(task, with_for_update=True)
                    if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                        return {"status": "SUPERSEDED", "task_id": task_id}

                    task.status = "WAITING_APPROVAL"
                    task.current_step = "Supervisor"
                    task.plan = final_state.get("plan")
                    task.plan_version = int(final_state.get("plan_version", task.plan_version))
                    task.plan_approved = False
                    task.resume_action = None
                    task.resume_payload = None
                    task.worker_lease_until = None
                    workflow_run.status = "WAITING_APPROVAL"
                    workflow_run.plan_version = task.plan_version
                    workflow_run.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info("Task %s: Paused at WAITING_APPROVAL. Worker lease released.", task_id)
                    return {"status": "WAITING_APPROVAL", "task_id": task_id}

                # Kiểm tra nếu graph dừng tại điểm chờ dữ liệu thực địa của người dùng (Gate G4)
                if pause_kind == "USER_DATA":
                    from app.services.provider_budget import pause_active_clock
                    await pause_active_clock(task.id)
                    await session.refresh(task, with_for_update=True)
                    if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                        return {"status": "SUPERSEDED", "task_id": task_id}

                    task.status = "WAITING_USER_DATA"
                    task.plan = final_state.get("plan", task.plan)
                    task.plan_version = int(final_state.get("plan_version", task.plan_version))
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
                    task.resume_action = None
                    task.resume_payload = None
                    workflow_run.status = "WAITING_USER_DATA"
                    workflow_run.plan_version = task.plan_version
                    workflow_run.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info("Task %s: Paused at WAITING_USER_DATA. Worker lease released.", task_id)
                    return {"status": "WAITING_USER_DATA", "task_id": task_id}

                report_content = final_state.get("final_report_markdown") if final_state else None
                if not report_content:
                    raise RuntimeError("Research graph completed without producing a report")

                await session.refresh(task, with_for_update=True)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}

                # Auto-approved runs need the same durable plan/contract identity
                # as interrupted runs. Persist only after the current claim fence.
                if isinstance(final_state.get("plan"), dict) and final_state["plan"]:
                    task.plan = final_state["plan"]
                    task.plan_version = int(final_state.get("plan_version", task.plan_version))

                report = await session.scalar(select(ResearchReport).where(ResearchReport.research_task_id == task.id))
                if report is None:
                    report = ResearchReport(research_task_id=task.id)
                    session.add(report)
                    await session.flush()
                last_version = await session.scalar(select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == report.id))
                review_metadata = final_state.get("critic_review_metadata") or {}
                article_title = next((line[2:].strip() for line in report_content.splitlines() if line.startswith("# ")), task.title)
                report_version = ReportVersion(
                    report_id=report.id,
                    version_number=(last_version or 0) + 1,
                    workflow_run_id=workflow_run.id,
                    plan_version=task.plan_version,
                    title=article_title[:255] if (task.plan or {}).get("manuscript_contract") else f"Báo cáo: {task.title}",
                    content_markdown=report_content,
                    executive_summary=final_state.get("executive_summary"),
                    review_status=review_metadata.get(
                        "status", "PASSED" if final_state.get("status") == "COMPLETED" else "NEEDS_REVIEW"
                    ),
                    review_metadata=review_metadata,
                    word_count=len(report_content.split()),
                )
                session.add(report_version)
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
                        report_version_id=report_version.id,
                        source_id=source_id,
                        chunk_id=chunk_id,
                        claim_id=claim_id,
                        citation_number=number,
                        citation_label=item.get("citation_label", f"[{number}]")[:500],
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

                    persisted_run_id = analysis_data.get("analysis_run_id")
                    if persisted_run_id:
                        run_record = await session.scalar(
                            select(AnalysisRun).where(
                                AnalysisRun.id == uuid.UUID(str(persisted_run_id)),
                                AnalysisRun.research_task_id == task.id,
                            ).with_for_update()
                        )
                        if run_record is None:
                            raise RuntimeError("Persisted experiment run is missing or belongs to another task")
                        run_record.routine_name = analysis_data.get("routine_name", run_record.routine_name)
                        run_record.status = analysis_data.get("status", "COMPLETED")
                        run_record.dataset_artifact_id = dataset_artifact_id
                        run_record.input_checksum = analysis_data.get("input_checksum")
                        run_record.manifest = analysis_data.get("manifest", {})
                        run_record.metrics = analysis_data.get("metrics")
                        run_record.reproducibility_status = analysis_data.get("reproducibility_status", "NOT_RUN")
                        run_record.reproducibility_diff = analysis_data.get("reproducibility_diff")
                        run_record.completed_at = datetime.now(timezone.utc)
                    else:
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
                    if persisted_run_id:
                        last_sequence = await session.scalar(
                            select(func.coalesce(func.max(ExperimentJournalEntry.sequence), 0)).where(
                                ExperimentJournalEntry.analysis_run_id == run_record.id
                            )
                        )
                        session.add(ExperimentJournalEntry(
                            research_task_id=task.id,
                            analysis_run_id=run_record.id,
                            sequence=int(last_sequence or 0) + 1,
                            kind="ARTIFACTS_PERSISTED",
                            actor="SYSTEM",
                            payload={"artifact_count": len(journal_art_ids)},
                            artifact_ids=journal_art_ids,
                        ))
                    else:
                        for entry in final_state.get("experiment_journal", []):
                            session.add(ExperimentJournalEntry(
                                research_task_id=task.id,
                                analysis_run_id=run_record.id,
                                sequence=entry["sequence"],
                                kind=entry["kind"],
                                actor=entry["actor"],
                                payload=entry.get("payload", {}),
                                artifact_ids=journal_art_ids,
                            ))

                from app.models.agent_run import AgentRun
                totals_res = await session.execute(
                    select(
                        func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0),
                        func.coalesce(func.sum(AgentRun.estimated_cost), 0.0),
                    ).where(AgentRun.research_task_id == task.id)
                )
                total_tokens, total_cost = totals_res.one()

                provider_usage = (task.budget_config or {}).get("_provider_usage") or {}
                provider_call_count = sum(
                    int(provider_usage.get(key, 0))
                    for key in ("llm_calls", "search_calls", "embedding_calls")
                )
                if provider_call_count:
                    task.total_tokens_used = int(provider_usage.get("input_tokens", 0)) + int(
                        provider_usage.get("output_tokens", 0)
                    )
                    task.total_cost_usd = round(float(provider_usage.get("cost_usd", 0)), 4)
                else:
                    task.total_tokens_used = int(total_tokens)
                    task.total_cost_usd = round(float(total_cost), 4)
                task.completed_at = datetime.now(timezone.utc)
                from app.services.provider_budget import pause_budget_config
                task.budget_config = pause_budget_config(task.budget_config, now=task.completed_at)
                final_status = final_state.get("status")
                task.status = "NEEDS_REVIEW" if final_status == "NEEDS_REVIEW" else "COMPLETED"
                task.worker_lease_until = None
                task.resume_action = None
                task.resume_payload = None
                workflow_run.status = task.status
                workflow_run.completed_at = datetime.now(timezone.utc)
                workflow_run.plan_version = task.plan_version
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
                await session.refresh(task, with_for_update=True)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}
                from app.services.provider_budget import ProviderBudgetExceeded, ResearchTaskStopped
                task.status = "NEEDS_REVIEW" if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)) else "FAILED"
                task.completed_at = datetime.now(timezone.utc)
                from app.services.provider_budget import pause_budget_config
                task.budget_config = pause_budget_config(task.budget_config, now=task.completed_at)
                task.worker_lease_until = None
                if isinstance(e, ProviderBudgetExceeded):
                    task.current_step = "BUDGET_LIMIT"
                # Detailed provider/runtime exceptions stay in server logs;
                # do not expose arbitrary exception text through task.description.
                error_msg = (
                    f"STOPPED: {str(e)}"
                    if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped))
                    else f"ERROR: Research workflow failed ({type(e).__name__})."
                )
                task.description = f"{task.description}\n\n{error_msg}" if task.description else error_msg
                task.resume_action = None
                task.resume_payload = None
                workflow_run.status = "NEEDS_REVIEW" if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)) else "FAILED"
                workflow_run.completed_at = datetime.now(timezone.utc)

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
    except Exception as exc:
        # Bootstrap/preload errors happen outside the graph's error handler.
        # Use a new transaction after rollback, and never overwrite a newer claim.
        if claim_attempt is not None:
            async with AsyncSessionLocal() as failure_session:
                async with failure_session.begin():
                    failed_task = await failure_session.scalar(select(ResearchTask).where(
                        ResearchTask.id == task_id, ResearchTask.status == "RUNNING",
                        ResearchTask.attempt_number == claim_attempt,
                    ).with_for_update())
                    if failed_task is not None:
                        failed_task.status = "FAILED"
                        failed_task.current_step = failed_task.current_step or "INITIALIZATION_FAILED"
                        failed_task.worker_lease_until = None
                        failed_task.completed_at = datetime.now(timezone.utc)
                        from app.services.provider_budget import pause_budget_config
                        failed_task.budget_config = pause_budget_config(failed_task.budget_config, now=failed_task.completed_at)
                        failed_task.resume_action = None
                        failed_task.resume_payload = None
                        summary = f"Research execution could not initialize/continue ({type(exc).__name__}). Check worker runtime logs."
                        failed_task.description = (failed_task.description or "") + "\n" + summary
                        if workflow_run_id is not None:
                            await failure_session.execute(update(WorkflowRun).where(
                                WorkflowRun.id == workflow_run_id,
                                WorkflowRun.research_task_id == failed_task.id,
                                WorkflowRun.status == "RUNNING",
                            ).values(status="FAILED", completed_at=failed_task.completed_at))
        logger.exception("Research execution failed task=%s attempt=%s", task_id, claim_attempt)
        raise
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Worker heartbeat stopped unexpectedly task=%s attempt=%s", task_id, claim_attempt)


@celery_app.task(bind=True, name="app.worker.execute_research_workflow")
def execute_research_workflow(self, task_id: str):
    """Task nền thực thi toàn bộ luồng Multi-Agent LangGraph cho một research task."""
    self.update_state(state="PROGRESS", meta={"message": "Khởi tạo LangGraph Engine"})

    result = run_worker_coroutine(run_langgraph_workflow(task_id))

    return result


async def run_document_ingestion(source_id: str) -> dict:
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


@celery_app.task(bind=True, name="app.worker.execute_document_ingestion")
def execute_document_ingestion(self, source_id: str):
    """Celery entry point for one PDF ingestion attempt."""
    self.update_state(state="PROGRESS", meta={"message": "Extracting and indexing document"})
    return run_worker_coroutine(run_document_ingestion(source_id))


async def run_task_deletion(task_id: str) -> dict:
    """Remove private files only after active research/ingestion leases expire."""
    task_uuid = uuid.UUID(task_id)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(
                select(ResearchTask).where(ResearchTask.id == task_uuid).with_for_update()
            )
            if task is None:
                return {"status": "DELETED", "task_id": task_id}
            if task.status != "DELETING":
                return {"status": "IGNORED", "task_id": task_id, "reason": "Task is not tombstoned"}
            outbox = await session.scalar(
                select(TaskDeletionOutbox)
                .where(TaskDeletionOutbox.research_task_id == task_uuid)
                .with_for_update()
            )
            if outbox is None:
                outbox = TaskDeletionOutbox(research_task_id=task_uuid)
                session.add(outbox)
                await session.flush()
            if outbox.cleanup_lease_until and outbox.cleanup_lease_until > now:
                return {"status": "ALREADY_CLAIMED", "task_id": task_id}
            active_ingestion = await session.scalar(
                select(func.count(ResearchSource.id)).where(
                    ResearchSource.research_task_id == task_uuid,
                    ResearchSource.ingestion_status == "PROCESSING",
                    ResearchSource.ingestion_lease_until > now,
                )
            )
            if (task.worker_lease_until and task.worker_lease_until > now) or active_ingestion:
                outbox.available_at = now + timedelta(seconds=15)
                outbox.dispatched_at = None
                outbox.locked_until = None
                outbox.cleanup_lease_until = None
                outbox.last_error = "Cleanup deferred while an active worker lease is running"
                return {"status": "DEFERRED", "task_id": task_id}
            outbox.cleanup_lease_until = now + timedelta(
                seconds=max(settings.WORKER_LEASE_SECONDS * 2, settings.OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS * 2)
            )
            outbox_id = outbox.id

    try:
        await asyncio.to_thread(artifact_store.delete_task_artifacts, task_uuid)
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                outbox = await session.get(TaskDeletionOutbox, outbox_id, with_for_update=True)
                if outbox is not None:
                    outbox.attempts += 1
                    retry_after = min(settings.OUTBOX_MAX_RETRY_SECONDS, settings.OUTBOX_RETRY_SECONDS * 2 ** min(outbox.attempts - 1, 10))
                    outbox.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    outbox.dispatched_at = None
                    outbox.locked_until = None
                    outbox.cleanup_lease_until = None
                    outbox.last_error = f"{type(exc).__name__}: {str(exc)[:1800]}"
        logger.exception("Task artifact cleanup failed task=%s; retained tombstone for retry", task_id)
        return {"status": "RETRY", "task_id": task_id}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(
                select(ResearchTask).where(ResearchTask.id == task_uuid).with_for_update()
            )
            if task is None:
                return {"status": "DELETED", "task_id": task_id}
            if task.status != "DELETING":
                return {"status": "RETRY", "task_id": task_id, "reason": "Tombstone changed during cleanup"}
            # No new worker can claim a tombstoned task; leases checked before
            # cleanup are static because both worker claim paths reject DELETING.
            await session.delete(task)
    logger.info("Deleted task and private artifacts task=%s", task_id)
    return {"status": "DELETED", "task_id": task_id}


@celery_app.task(bind=True, name="app.worker.execute_task_deletion")
def execute_task_deletion(self, task_id: str):
    self.update_state(state="PROGRESS", meta={"message": "Cleaning up deleted research task"})
    return run_worker_coroutine(run_task_deletion(task_id))
