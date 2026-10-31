import io
import json
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents import nodes
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.report import ResearchReport, ReportVersion, ExportArtifact
from app.models.task import ResearchTask
from app.services import experiment_bundle as bundles
from app.services.artifact_store import ArtifactStore
from tests.test_report_versions import _register_and_login


@pytest.fixture(autouse=True)
def isolated_bundle_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(bundles, "artifact_store", ArtifactStore(str(tmp_path / "storage")))


async def create_experiment(client, *, negative=False):
    suffix = uuid.uuid4().hex[:10]
    owner = await _register_and_login(client, "bundle_" + suffix)
    other = await _register_and_login(client, "otherbundle_" + suffix)
    response = await client.post("/api/v1/research", headers=owner, json={
        "title": "Replay study", "research_question": "Can an experiment be replayed from a frozen report version?",
        "research_type": "EMPIRICAL_COMPUTATIONAL"})
    assert response.status_code == 201, response.text
    tid = uuid.UUID(response.json()["id"])
    csv = "x,target\r\n" + "\r\n".join(f"{1 if negative else i},{i * 3 + 2}" for i in range(30))
    state = await nodes.experiment_runner_node({"task_id": str(tid), "dataset_csv": csv})
    async with AsyncSessionLocal() as db:
        report = ResearchReport(research_task_id=tid); db.add(report); await db.flush()
        version = ReportVersion(report_id=report.id, version_number=1, title="Original experiment",
            content_markdown="# Original experiment\n\nExploratory findings.", review_metadata={
                "manuscript_input_snapshot": {"research_type": "EMPIRICAL_COMPUTATIONAL", "analysis_run": state["analysis_run"]}})
        db.add(version); await db.commit()
        vid, rid = version.id, report.id
    url = f"/api/v1/research/{tid}/report/versions/1/experiment-bundle"
    return owner, other, tid, vid, rid, state, csv, url


@pytest.mark.asyncio
@pytest.mark.parametrize("negative", [False, True])
async def test_private_version_bundle_replays_without_project_dependencies(tmp_path, negative):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner, other, tid, vid, _, state, csv, url = await create_experiment(client, negative=negative)
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=other)).status_code == 404
        info = await client.get(url + "/availability", headers=owner)
        assert info.json()["available"] and "no-store" in info.headers["cache-control"]
        response = await client.get(url, headers=owner)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert "no-store" in response.headers["cache-control"]
        unpack = tmp_path / "unpacked"; unpack.mkdir()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.read("input.csv") == csv.encode()
            manifest = json.loads(archive.read("bundle_manifest.json"))
            assert manifest["report_version_id"] == str(vid)
            assert manifest["analysis_run_id"] == state["analysis_run"]["analysis_run_id"]
            journal = json.loads(archive.read("journal.json"))
            assert [e["sequence"] for e in journal] == [1, 2, 3, 4, 5, 6]
            assert json.loads(archive.read("expected_result.json"))["raw_metrics"]
            assert b"<svg" in archive.read("predicted-vs-actual.svg")
            if negative:
                assert json.loads(archive.read("metrics.json"))["comparison"]["verdict"] == "NO_IMPROVEMENT"
            assert all("/" not in name and "\\" not in name for name in archive.namelist())
            archive.extractall(unpack)
        run = subprocess.run([sys.executable, "-I", str(unpack / "reproduce.py")], capture_output=True, text=True, timeout=20)
        assert run.returncode == 0, run.stdout + run.stderr
        comparison = json.loads((unpack / "reproduced/comparison.json").read_text())
        assert comparison["passed"]
        assert (unpack / "reproduced/residuals.svg").exists()
        assert (unpack / "reproduced/predicted-vs-actual.svg").exists()
        original = (unpack / "input.csv").read_bytes()
        (unpack / "input.csv").write_bytes(original + b"\n")
        run = subprocess.run([sys.executable, "-I", str(unpack / "reproduce.py")], capture_output=True, text=True, timeout=20)
        assert run.returncode == 2 and "Integrity check failed" in run.stdout


@pytest.mark.asyncio
async def test_export_uses_original_run_after_newer_data_and_report_exist():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner, _, tid, vid, rid, _, csv, url = await create_experiment(client)
        newer = await nodes.experiment_runner_node({"task_id": str(tid), "dataset_csv": csv.replace("x,target", "changed,target")})
        async with AsyncSessionLocal() as db:
            db.add(ReportVersion(report_id=rid, version_number=2, title="Newer experiment", content_markdown="# Newer",
                review_metadata={"manuscript_input_snapshot": {"research_type": "EMPIRICAL_COMPUTATIONAL", "analysis_run": newer["analysis_run"]}}))
            await db.commit()
        response = await client.get(url, headers=owner)
        assert response.status_code == 200, response.text
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.read("input.csv") == csv.encode()
            assert json.loads(archive.read("bundle_manifest.json"))["report_version_id"] == str(vid)
            assert "Newer experiment" not in archive.read("manuscript.md").decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["tampered_input", "missing_code", "cross_task_artifact", "changed_result", "failed_run", "deleting"])
async def test_export_rejects_integrity_scope_and_lifecycle_failures(failure):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner, _, tid, _, _, state, _, url = await create_experiment(client)
        async with AsyncSessionLocal() as db:
            run = await db.get(AnalysisRun, uuid.UUID(state["analysis_run"]["analysis_run_id"]))
            entry = await db.scalar(select(ExperimentJournalEntry).where(ExperimentJournalEntry.analysis_run_id == run.id,
                                                                       ExperimentJournalEntry.kind == "PLAN_FROZEN"))
            snapshot = entry.payload["reproduction_snapshot"]
            ref = snapshot["routine"] if failure == "missing_code" else snapshot["input"]
            artifact = await db.get(ExportArtifact, uuid.UUID(ref["artifact_id"]))
            if failure == "tampered_input":
                bundles.artifact_store.get_artifact_path(tid, artifact.file_path).write_bytes(b"changed")
            elif failure == "missing_code":
                bundles.artifact_store.get_artifact_path(tid, artifact.file_path).unlink()
            elif failure == "cross_task_artifact":
                foreign = ResearchTask(user_id=(await db.get(ResearchTask, tid)).user_id, title="Other", research_question="Other task")
                db.add(foreign); await db.flush(); artifact.research_task_id = foreign.id
            elif failure == "changed_result":
                run.metrics = {"fabricated": True}
            elif failure == "failed_run":
                run.status = "FAILED"
            elif failure == "deleting":
                (await db.get(ResearchTask, tid)).status = "DELETING"
            await db.commit()
        response = await client.get(url, headers=owner)
        assert response.status_code == (404 if failure == "deleting" else 409), response.text


@pytest.mark.asyncio
async def test_historical_experiment_never_substitutes_current_routine():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner, _, tid, _, rid, state, _, _ = await create_experiment(client)
        async with AsyncSessionLocal() as db:
            old_run = AnalysisRun(research_task_id=tid, status="COMPLETED", manifest=state["analysis_run"]["manifest"],
                metrics=state["analysis_run"]["metrics"], completed_at=datetime.now(timezone.utc))
            db.add(old_run); await db.flush()
            historical = {**state["analysis_run"], "analysis_run_id": str(old_run.id)}
            db.add(ReportVersion(report_id=rid, version_number=2, title="Historical", content_markdown="# Historical", review_metadata={
                "manuscript_input_snapshot": {"research_type": "EMPIRICAL_COMPUTATIONAL", "analysis_run": historical}}))
            await db.commit()
        url = f"/api/v1/research/{tid}/report/versions/2/experiment-bundle"
        assert (await client.get(url, headers=owner)).status_code == 409
        assert (await client.get(url + "/availability", headers=owner)).json()["available"] is False


@pytest.mark.asyncio
async def test_journal_is_cut_off_at_the_requested_report_version():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner, _, tid, _, _, state, _, url = await create_experiment(client)
        async with AsyncSessionLocal() as db:
            db.add(ExperimentJournalEntry(research_task_id=tid,
                analysis_run_id=uuid.UUID(state["analysis_run"]["analysis_run_id"]), sequence=7,
                kind="INTERPRETATION", actor="USER", payload={"note": "Later correction outside the old version"}))
            await db.commit()
        response = await client.get(url, headers=owner)
        assert response.status_code == 200, response.text
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert len(json.loads(archive.read("journal.json"))) == 6


@pytest.mark.asyncio
async def test_frozen_input_and_code_exist_before_the_runner_starts(monkeypatch):
    from app.services import isolated_experiment
    original = isolated_experiment.run_tabular_regression_isolated
    seen = []
    async def observe(dataset_csv, **kwargs):
        async with AsyncSessionLocal() as db:
            entry = await db.scalar(select(ExperimentJournalEntry).join(AnalysisRun,
                ExperimentJournalEntry.analysis_run_id == AnalysisRun.id).where(
                    ExperimentJournalEntry.kind == "PLAN_FROZEN", AnalysisRun.status == "STARTED")
                .order_by(AnalysisRun.created_at.desc()).limit(1))
            snap = entry.payload["reproduction_snapshot"]
            content = await bundles.read_snapshot(db, entry.research_task_id, snap["input"], "REPRO_INPUT", 5 * 1024 * 1024)
            assert content == dataset_csv.encode()
            assert await bundles.read_snapshot(db, entry.research_task_id, snap["routine"], "REPRO_CODE", 200_000)
            seen.append(True)
        return await original(dataset_csv, **kwargs)
    monkeypatch.setattr(isolated_experiment, "run_tabular_regression_isolated", observe)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await create_experiment(client)
    assert seen == [True]
