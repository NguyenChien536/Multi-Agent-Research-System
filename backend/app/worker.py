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
from app.models.task import ResearchTask, TaskDispatchOutbox, WorkflowRun
from app.models.source import DocumentChunk, ResearchSource
from app.models.report import ExportArtifact, ResearchReport
from app.models.grounding import Citation, ClaimEvidence, Evidence, ResearchClaim
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.user import User
from app.agents.graph import research_graph, build_research_graph
from app.agents.state import ResearchState
from app.services.artifact_store import artifact_store
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
        await checkpointer.setup()
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
            checkpoint_update = {"attempt_number": task.attempt_number}
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
            Command(update={"attempt_number": task.attempt_number}), config=config
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
            from app.services.provider_budget import resume_active_clock
            await resume_active_clock(task.id)

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
                    await session.refresh(task)
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
                    await session.refresh(task)
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

                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}

                report = ResearchReport(
                    research_task_id=task.id,
                    title=f"Báo cáo: {task.title}",
                    content_markdown=report_content,
                    review_status=(final_state.get("critic_review_metadata") or {}).get(
                        "status", "PASSED" if final_state.get("status") == "COMPLETED" else "NEEDS_REVIEW"
                    ),
                    review_metadata=(final_state.get("critic_review_metadata") or {}),
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
                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}
                from app.services.provider_budget import ProviderBudgetExceeded, ResearchTaskStopped
                task.status = "NEEDS_REVIEW" if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)) else "FAILED"
                task.completed_at = datetime.now(timezone.utc)
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
