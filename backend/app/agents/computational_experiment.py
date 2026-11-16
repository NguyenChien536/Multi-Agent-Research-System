"""Computational experiment node: frozen plan, isolated run, journal, and failure record."""

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import func, select

from app.agents.state import ResearchState

logger = logging.getLogger(__name__)

async def run_computational_experiment(
    state: ResearchState, *, record_progress, record_run
) -> Dict[str, Any]:
    """
    Experiment Runner Node (Phase 5):
    - Chạy routine tính toán chuẩn tabular_regression_v1 cho bài nghiên cứu dạng EMPIRICAL_COMPUTATIONAL.
    - Chỉ sử dụng dataset_csv do người dùng nạp; không tạo dữ liệu giả cho bài nghiên cứu.
    - Thực hiện kiểm tái lập (repeatability verification) tự động bằng lần chạy thứ hai từ cùng manifest.
    - Sinh các mục sổ nhật ký thí nghiệm ExperimentJournalEntry (append-only) theo chuẩn ADR-005.
    """
    await record_progress(state, "EXPERIMENT_RUNNER")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = "tabular_regression_v1_engine"

    task_id_str = state.get("task_id")
    dataset_csv = state.get("dataset_csv")

    from app.services.experiment_runner import (
        InvalidInputError,
        build_tabular_regression_manifest,
    )
    from app.services.isolated_experiment import (
        run_tabular_regression_isolated,
        verify_tabular_repeatability_isolated,
    )

    analysis_run_id: str | None = None
    frozen_manifest: Dict[str, Any] | None = None
    reproduction_snapshot = None
    try:
        if not dataset_csv:
            raise InvalidInputError("A user-provided CSV dataset is required for computational empirical analysis")

        frozen_manifest = await asyncio.to_thread(build_tabular_regression_manifest, dataset_csv, seed=42)
        dataset_artifact_id = state.get("dataset_artifact_id")
        parsed_dataset_artifact_id = uuid.UUID(str(dataset_artifact_id)) if dataset_artifact_id else None

        # Write the immutable plan and STARTED attempt before computation. A
        # worker crash will leave visible evidence that the attempt began.
        if task_id_str:
            from app.core.database import AsyncSessionLocal
            from app.models.experiment import AnalysisRun, ExperimentJournalEntry

            async with AsyncSessionLocal() as session:
                run_record = AnalysisRun(
                    research_task_id=uuid.UUID(str(task_id_str)),
                    routine_name="tabular_regression_v1",
                    status="STARTED",
                    dataset_artifact_id=parsed_dataset_artifact_id,
                    input_checksum=frozen_manifest["input_checksum"],
                    manifest=frozen_manifest,
                    reproducibility_status="NOT_RUN",
                )
                session.add(run_record)
                await session.flush()
                analysis_run_id = str(run_record.id)
                from app.services.experiment_bundle import freeze_reproduction_inputs
                reproduction_snapshot = await freeze_reproduction_inputs(
                    session, run_record.research_task_id, run_record.id, dataset_csv)
                session.add_all([
                    ExperimentJournalEntry(
                        research_task_id=run_record.research_task_id,
                        analysis_run_id=run_record.id,
                        sequence=1,
                        kind="PLAN_FROZEN",
                        actor="METHODOLOGIST",
                        payload={"manifest": frozen_manifest, "reproduction_snapshot": reproduction_snapshot},
                        artifact_ids=([str(parsed_dataset_artifact_id)] if parsed_dataset_artifact_id else []) +
                            [reproduction_snapshot["input"]["artifact_id"], reproduction_snapshot["routine"]["artifact_id"]],
                    ),
                    ExperimentJournalEntry(
                        research_task_id=run_record.research_task_id,
                        analysis_run_id=run_record.id,
                        sequence=2,
                        kind="STARTED",
                        actor="SYSTEM",
                        payload={
                            "routine_name": "tabular_regression_v1",
                            "input_checksum": frozen_manifest["input_checksum"],
                            "started_at": started_at.isoformat(),
                        },
                        artifact_ids=[str(parsed_dataset_artifact_id)] if parsed_dataset_artifact_id else [],
                    ),
                ])
                await session.commit()

        params = frozen_manifest["parameters"]
        if reproduction_snapshot:
            from app.services.experiment_bundle import assert_frozen_routine
            assert_frozen_routine(reproduction_snapshot)
        run_result = await run_tabular_regression_isolated(
            dataset_csv,
            target_column=frozen_manifest["target_column"],
            feature_columns=frozen_manifest["feature_columns"],
            alpha=params["alpha"],
            test_size=params["test_size"],
            seed=params["seed"],
        )
        if run_result.get("manifest") != frozen_manifest:
            raise RuntimeError("Executed routine manifest differs from the pre-run frozen plan")
        passed, diff = await verify_tabular_repeatability_isolated(dataset_csv, run_result)
        if reproduction_snapshot:
            assert_frozen_routine(reproduction_snapshot)
        completed_at = datetime.now(timezone.utc)

        analysis_run = {
            "analysis_run_id": analysis_run_id,
            "routine_name": "tabular_regression_v1",
            "status": "COMPLETED",
            "input_checksum": run_result["input_checksum"],
            "manifest": run_result["manifest"],
            "metrics": run_result["metrics"],
            "chart_data": run_result["chart_data"],
            "reproducibility_status": "PASSED" if passed else "FAILED",
            "reproducibility_diff": diff,
            "readme_markdown": run_result["readme_markdown"],
        }

        journal_entries = [
            {
                "sequence": 1,
                "kind": "PLAN_FROZEN",
                "actor": "METHODOLOGIST",
                "payload": {
                    "routine_name": "tabular_regression_v1",
                    "manifest": run_result["manifest"],
                },
            },
            {
                "sequence": 2,
                "kind": "STARTED",
                "actor": "SYSTEM",
                "payload": {
                    "routine_name": "tabular_regression_v1",
                    "input_checksum": run_result["input_checksum"],
                },
            },
            {
                "sequence": 3,
                "kind": "EXECUTION_RESULT",
                "actor": "SYSTEM",
                "payload": {
                    "status": "COMPLETED",
                    "metrics": run_result["metrics"],
                },
            },
            {
                "sequence": 4,
                "kind": "OBSERVATION",
                "actor": "SYSTEM",
                "payload": {
                    "verdict": run_result["verdict"],
                    "comparison": run_result["metrics"]["comparison"],
                },
            },
            {
                "sequence": 5,
                "kind": "REPRODUCTION_CHECK",
                "actor": "SYSTEM",
                "payload": {
                    "status": "PASSED" if passed else "FAILED",
                    "tolerance": diff["tolerance"],
                    "diff": diff,
                },
            },
            {
                "sequence": 6,
                "kind": "INTERPRETATION",
                "actor": "DATA_ANALYST",
                "payload": {
                    "summary": f"Routine tabular_regression_v1 hoàn thành với kết luận {run_result['verdict']}. Ridge MAE: {run_result['metrics']['model']['mae']} so với Baseline MAE: {run_result['metrics']['baseline']['mae']}. Phép kiểm tái lập: {'ĐẠT (PASSED)' if passed else 'KHÔNG ĐẠT (FAILED)'}. Kết quả mang tính chất dự đoán và thăm dò, không suy luận quan hệ nhân quả.",
                },
            },
        ]

        if task_id_str and analysis_run_id:
            from app.core.database import AsyncSessionLocal
            from app.models.experiment import AnalysisRun, ExperimentJournalEntry

            async with AsyncSessionLocal() as session:
                persisted_run = await session.get(AnalysisRun, uuid.UUID(analysis_run_id))
                if not persisted_run or persisted_run.research_task_id != uuid.UUID(str(task_id_str)):
                    raise RuntimeError("Pre-run analysis record disappeared or changed owner")
                persisted_run.status = "COMPLETED"
                persisted_run.manifest = run_result["manifest"]
                persisted_run.metrics = run_result["metrics"]
                persisted_run.reproducibility_status = analysis_run["reproducibility_status"]
                persisted_run.reproducibility_diff = diff
                persisted_run.completed_at = completed_at
                from app.services.experiment_bundle import save_snapshot_file, json_bytes
                result_ref = await save_snapshot_file(session, persisted_run.research_task_id,
                    f"result-{analysis_run_id}.json", json_bytes(run_result), "REPRO_RESULT")
                journal_entries[2]["payload"]["reproduction_result"] = result_ref
                session.add_all([
                    ExperimentJournalEntry(
                        research_task_id=persisted_run.research_task_id,
                        analysis_run_id=persisted_run.id,
                        sequence=entry["sequence"],
                        kind=entry["kind"],
                        actor=entry["actor"],
                        payload=entry["payload"],
                        artifact_ids=([str(persisted_run.dataset_artifact_id)] if persisted_run.dataset_artifact_id else []) +
                            ([result_ref["artifact_id"]] if entry["kind"] == "EXECUTION_RESULT" else []),
                    )
                    for entry in journal_entries[2:]
                ])
                await session.commit()

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = completed_at or datetime.now(timezone.utc)

        await record_run(
            task_id=task_id_str,
            agent_name="ExperimentRunner",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"rows": run_result["manifest"]["dataset_rows"]},
            output_summary={"verdict": run_result["verdict"], "repeatability": "PASSED" if passed else "FAILED"},
            tool_calls=[{"tool": "tabular_regression_v1"}],
        )

        return {
            "current_agent": "experiment_runner",
            "dataset_csv": dataset_csv,
            "analysis_run": analysis_run,
            "experiment_journal": journal_entries,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_run(
            task_id=task_id_str,
            agent_name="ExperimentRunner",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        # A failed execution is a technical failure, not a negative scientific
        # result. Preserve a failed AnalysisRun and append-only journal entries
        # even though the graph cannot continue to Writer.
        if task_id_str:
            try:
                from app.core.database import AsyncSessionLocal
                from app.models.experiment import AnalysisRun, ExperimentJournalEntry

                checksum = (
                    hashlib.sha256(dataset_csv.strip().encode("utf-8")).hexdigest()
                    if dataset_csv
                    else None
                )
                dataset_artifact_id = state.get("dataset_artifact_id")
                try:
                    parsed_dataset_artifact_id = (
                        uuid.UUID(str(dataset_artifact_id)) if dataset_artifact_id else None
                    )
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid dataset artifact ID for task %s", task_id_str)
                    parsed_dataset_artifact_id = None
                safe_error = f"{type(exc).__name__}: {str(exc)[:500]}"
                async with AsyncSessionLocal() as session:
                    failed_run = await session.get(AnalysisRun, uuid.UUID(analysis_run_id)) if analysis_run_id else None
                    if failed_run is None:
                        failed_run = AnalysisRun(
                            research_task_id=uuid.UUID(str(task_id_str)),
                            routine_name="tabular_regression_v1",
                            status="FAILED",
                            dataset_artifact_id=parsed_dataset_artifact_id if "parsed_dataset_artifact_id" in locals() else None,
                            input_checksum=checksum,
                            manifest=frozen_manifest or {
                                "manifest_version": "1.0",
                                "routine_name": "tabular_regression_v1",
                                "input_checksum": checksum,
                                "parameters": {"seed": 42},
                            },
                            reproducibility_status="NOT_RUN",
                        )
                        session.add(failed_run)
                        await session.flush()
                    failed_run.status = "FAILED"
                    failed_run.error_message = safe_error
                    failed_run.completed_at = datetime.now(timezone.utc)
                    current_sequence = await session.scalar(
                        select(func.coalesce(func.max(ExperimentJournalEntry.sequence), 0)).where(
                            ExperimentJournalEntry.analysis_run_id == failed_run.id
                        )
                    )
                    failure_kind = "INVALID_INPUT" if isinstance(exc, InvalidInputError) else "TECHNICAL_FAILURE"
                    session.add(ExperimentJournalEntry(
                        research_task_id=failed_run.research_task_id,
                        analysis_run_id=failed_run.id,
                        sequence=int(current_sequence or 0) + 1,
                        kind="EXECUTION_RESULT",
                        actor="SYSTEM",
                        payload={"status": failure_kind, "error": safe_error},
                        artifact_ids=[str(failed_run.dataset_artifact_id)] if failed_run.dataset_artifact_id else [],
                    ))
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist technical experiment failure for task %s", task_id_str)
        raise
