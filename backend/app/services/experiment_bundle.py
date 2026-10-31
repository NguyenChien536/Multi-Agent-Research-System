"""Private reproducibility snapshots and version-bound archives; no code execution."""
import hashlib
import io
import json
import platform
import sys
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.report import ExportArtifact
from app.services.artifact_store import artifact_store

MAX_BUNDLE_BYTES = 12 * 1024 * 1024


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")


def checksum(data):
    return hashlib.sha256(data).hexdigest()


async def save_snapshot_file(db, task_id, name, content, kind):
    saved = artifact_store.save_artifact(task_id, name, content)
    artifact = ExportArtifact(research_task_id=task_id, export_type=kind,
                              file_path=saved["file_path"], file_size_bytes=len(content))
    db.add(artifact)
    await db.flush()
    return {"artifact_id": str(artifact.id), "sha256": checksum(content), "size_bytes": len(content)}


async def freeze_reproduction_inputs(db, task_id, run_id, dataset_csv):
    """Persist exact execution input and trusted code before PLAN_FROZEN commits."""
    source = Path(__file__).with_name("experiment_runner.py").read_bytes()
    dataset = dataset_csv.encode("utf-8")
    return {"schema_version": 1,
            "input": await save_snapshot_file(db, task_id, f"repro-{run_id}.csv", dataset, "REPRO_INPUT"),
            "routine": await save_snapshot_file(db, task_id, f"routine-{run_id}.py", source, "REPRO_CODE"),
            "environment": {"python_version": platform.python_version(), "implementation": sys.implementation.name,
                            "platform": platform.platform(), "dependencies": "Python standard library only"}}


def assert_frozen_routine(snapshot):
    if checksum(Path(__file__).with_name("experiment_runner.py").read_bytes()) != snapshot["routine"]["sha256"]:
        raise RuntimeError("Routine changed during execution; no reproducible result can be published")


async def bundle_records(db, task, version):
    snapshot = (version.review_metadata or {}).get("manuscript_input_snapshot") or {}
    analysis = snapshot.get("analysis_run") or {}
    if snapshot.get("research_type") != "EMPIRICAL_COMPUTATIONAL" or not analysis.get("analysis_run_id"):
        raise HTTPException(409, "This report version has no computational experiment snapshot")
    try:
        run_id = uuid.UUID(str(analysis["analysis_run_id"]))
    except ValueError as exc:
        raise HTTPException(409, "Invalid historical analysis identity") from exc
    run = await db.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.research_task_id == task.id))
    if (not run or run.status != "COMPLETED" or analysis.get("status") != "COMPLETED"
            or not run.completed_at or run.completed_at > version.created_at
            or run.manifest != analysis.get("manifest") or run.metrics != analysis.get("metrics")):
        raise HTTPException(409, "Analysis does not match the completed experiment in this report version")
    entries = list(await db.scalars(select(ExperimentJournalEntry).where(
        ExperimentJournalEntry.analysis_run_id == run.id, ExperimentJournalEntry.research_task_id == task.id,
        ExperimentJournalEntry.created_at <= version.created_at).order_by(ExperimentJournalEntry.sequence).limit(257)))
    if len(entries) > 256:
        raise HTTPException(409, "Experiment journal exceeds the export limit")
    frozen = next((e for e in entries if e.kind == "PLAN_FROZEN"), None)
    completed = next((e for e in entries if e.kind == "EXECUTION_RESULT" and e.payload.get("status") == "COMPLETED"), None)
    reproduction = (frozen.payload.get("reproduction_snapshot") or {}) if frozen else {}
    result_ref = completed.payload.get("reproduction_result") if completed else None
    if (reproduction.get("schema_version") != 1 or not reproduction.get("input") or not reproduction.get("routine")
            or not (reproduction.get("environment") or {}).get("python_version")
            or not result_ref or frozen.payload.get("manifest") != analysis["manifest"]):
        raise HTTPException(409, "Historical experiment lacks frozen code/input/result snapshots; run a new experiment to enable replay export")
    return analysis, entries, reproduction, result_ref


async def read_snapshot(db, task_id, ref, kind, limit):
    try:
        artifact_id = uuid.UUID(str(ref["artifact_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "Invalid experiment artifact identity") from exc
    artifact = await db.scalar(select(ExportArtifact).where(ExportArtifact.id == artifact_id,
        ExportArtifact.research_task_id == task_id, ExportArtifact.export_type == kind))
    if not artifact:
        raise HTTPException(409, "Experiment artifact is missing or belongs to another task")
    path = artifact_store.get_artifact_path(task_id, artifact.file_path)
    if not path:
        raise HTTPException(409, "Experiment artifact file is unavailable")
    try:
        with path.open("rb") as handle:
            content = handle.read(limit + 1)
    except OSError as exc:
        raise HTTPException(409, "Experiment artifact file is unavailable") from exc
    if (len(content) > limit or len(content) != artifact.file_size_bytes or len(content) != ref.get("size_bytes")
            or checksum(content) != ref.get("sha256")):
        raise HTTPException(409, "Experiment artifact integrity verification failed")
    return content


async def build_experiment_bundle(db, task, version):
    analysis, entries, frozen, result_ref = await bundle_records(db, task, version)
    files = {
        "input.csv": await read_snapshot(db, task.id, frozen.get("input"), "REPRO_INPUT", 5 * 1024 * 1024),
        "routine.py": await read_snapshot(db, task.id, frozen.get("routine"), "REPRO_CODE", 200_000),
        "expected_result.json": await read_snapshot(db, task.id, result_ref, "REPRO_RESULT", 1_000_000),
    }
    try:
        result = json.loads(files["expected_result.json"])
        normalized = files["input.csv"].decode("utf-8").strip().encode("utf-8")
        if (not isinstance(result, dict) or result.get("status") != "COMPLETED" or result.get("manifest") != analysis["manifest"]
                or result.get("metrics") != analysis["metrics"] or result.get("input_checksum") != checksum(normalized)
                or result.get("input_checksum") != analysis["manifest"].get("input_checksum")):
            raise ValueError("Snapshot mismatch")
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        raise HTTPException(409, "Result/input snapshot does not match the report's frozen analysis") from exc
    from app.services.reproduction_launcher import scatter_svg
    try:
        plots = {"predicted-vs-actual.svg": scatter_svg(result["chart_data"]["samples"]).encode("utf-8"),
                 "residuals.svg": scatter_svg(result["chart_data"]["samples"], True).encode("utf-8")}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "Measured chart data is unavailable or invalid") from exc
    files.update(plots)
    files.update({
        "reproduce.py": Path(__file__).with_name("reproduction_launcher.py").read_bytes(),
        "config.json": json_bytes(analysis["manifest"]),
        "metrics.json": json_bytes(result["metrics"]),
        "chart_data.json": json_bytes(result["chart_data"]),
        "environment.json": json_bytes(frozen["environment"]),
        "journal.json": json_bytes([{"sequence": e.sequence, "kind": e.kind, "actor": e.actor,
            "payload": e.payload, "artifact_ids": e.artifact_ids, "created_at": e.created_at.isoformat()} for e in entries]),
        "manuscript.md": version.content_markdown.encode("utf-8"),
        "README.md": (
            "# Experiment reproducibility bundle\n\n"
            "Contains the input dataset: keep this archive private. Extract to a new directory and run "
            "`python reproduce.py` using the recorded CPython version. No API key, network access or pip install is needed. "
            "Run only bundles you trust; the included routine is project-owned Python code, not an arbitrary-code sandbox.\n\n"
            "The launcher verifies file hashes, runs the frozen routine and writes results, comparison JSON, "
            "and SVG plots to `reproduced/`. A nonzero exit means integrity, environment or replay failed. "
            "Original files are preserved. Charts show at most 50 held-out observations; their data is included.\n\n"
            "This archive is pinned to one report version and one analysis run. Its journal is limited to entries "
            "recorded by that version's creation time; later runs are excluded. Negative results and failed "
            "repeatability checks are retained. Replay agreement is technical repeatability, not independent "
            "scientific validation or evidence of superiority. Hashes detect changed files, not a maliciously "
            "rewritten archive/manifest. Historical runs missing snapshots are never filled from current code.\n"
        ).encode("utf-8"),
    })
    manifest = {"schema_version": 1, "report_version_id": str(version.id), "version_number": version.version_number,
                "analysis_run_id": analysis["analysis_run_id"], "review_status": version.review_status,
                "reproducibility_status": analysis.get("reproducibility_status", "NOT_RUN"),
                "journal_cutoff": version.created_at.isoformat(), "checksums": {k: checksum(v) for k, v in files.items()}}
    files["bundle_manifest.json"] = json_bytes(manifest)
    if sum(map(len, files.values())) > MAX_BUNDLE_BYTES:
        raise HTTPException(409, "Experiment bundle exceeds the export size limit")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()
