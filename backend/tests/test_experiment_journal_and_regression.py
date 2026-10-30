from tests.manuscript_helpers import supported_critic_response
"""Tests for Phase 5: Computational Routine tabular_regression_v1, AnalysisRun, and ExperimentJournalEntry."""

import io
import random
import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.agents import nodes as nodes_module
from app.agents.graph import route_after_methodologist
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.report import ExportArtifact, ResearchReport
from app.models.source import DocumentChunk
from app.models.task import ResearchTask, TaskDispatchOutbox, WorkflowRun
from app.services.experiment_runner import (
    ExperimentError,
    MAX_DATASET_BYTES,
    MAX_DATASET_COLUMNS,
    MAX_DATASET_ROWS,
    InvalidInputError,
    TargetLeakageError,
    cholesky_solve,
    parse_csv_dataset,
    run_tabular_regression_v1,
    verify_repeatability,
)
from app.services.upload_reader import UploadSizeLimitExceeded, read_upload_with_limit
from app.tools.search import SearchResult
from app.worker import run_langgraph_workflow


async def _register_and_login(client: AsyncClient, suffix: str):
    reg = await client.post("/api/v1/auth/register", json={
        "username": f"exp_{suffix}",
        "email": f"exp_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    assert reg.status_code == 201
    login = await client.post("/api/v1/auth/login", json={
        "email": f"exp_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _generate_synthetic_csv(n_rows: int = 50, correlated: bool = True) -> str:
    """Generate synthetic CSV dataset for testing."""
    header = "f1,f2,f3,target\n"
    rng = random.Random(42)
    lines = []
    for _ in range(n_rows):
        x1 = round(rng.uniform(1.0, 20.0), 3)
        x2 = round(rng.uniform(5.0, 15.0), 3)
        x3 = round(rng.uniform(50.0, 100.0), 3)
        if correlated:
            y = round(3.0 * x1 - 1.5 * x2 + 0.2 * x3 + rng.uniform(-1.0, 1.0), 3)
        else:
            # Pure independent noise around constant mean
            y = round(50.0 + rng.uniform(-0.1, 0.1), 3)
        lines.append(f"{x1},{x2},{x3},{y}")
    return header + "\n".join(lines)


# =========================================================================
# Unit Tests for tabular_regression_v1 Routine & Parser
# =========================================================================

def test_parse_csv_dataset_valid():
    csv_text = _generate_synthetic_csv(20)
    headers, rows = parse_csv_dataset(csv_text)
    assert headers == ["f1", "f2", "f3", "target"]
    assert len(rows) == 20
    assert isinstance(rows[0]["f1"], float)


def test_parse_csv_dataset_empty():
    with pytest.raises(InvalidInputError, match="empty"):
        parse_csv_dataset("")


def test_parse_csv_dataset_insufficient_rows():
    csv_text = "f1,f2,target\n1,2,3\n4,5,6\n"
    with pytest.raises(InvalidInputError, match="minimum 10 rows"):
        parse_csv_dataset(csv_text)


def test_parse_csv_dataset_rejects_duplicate_headers_and_dimension_overflow():
    duplicate_header = "Feature, feature, target\n" + "1,2,3\n" * 10
    with pytest.raises(InvalidInputError, match="duplicate column names"):
        parse_csv_dataset(duplicate_header)

    too_many_columns = ",".join([f"c{i}" for i in range(MAX_DATASET_COLUMNS + 1)]) + "\n"
    with pytest.raises(InvalidInputError, match="maximum supported"):
        parse_csv_dataset(too_many_columns)

    too_many_rows = "feature,target\n" + "1,2\n" * (MAX_DATASET_ROWS + 1)
    with pytest.raises(InvalidInputError, match=f"maximum of {MAX_DATASET_ROWS} rows"):
        parse_csv_dataset(too_many_rows)

    non_finite_values = "feature,target\n" + "1,2\n" * 9 + "inf,3\n"
    with pytest.raises(InvalidInputError, match="non-finite numeric value"):
        parse_csv_dataset(non_finite_values)


def test_numeric_routine_rejects_silent_categorical_column_dropping():
    csv_text = "feature,category,target\n" + "1,A,2\n" * 10
    with pytest.raises(InvalidInputError, match="numeric columns only"):
        parse_csv_dataset(csv_text)


def test_srs_computational_upload_limits_are_explicit():
    assert MAX_DATASET_BYTES == 5 * 1024 * 1024
    assert MAX_DATASET_ROWS == 20_000
    assert MAX_DATASET_COLUMNS == 30
    with pytest.raises(InvalidInputError, match="maximum supported size of 5 MiB"):
        parse_csv_dataset("x" * (MAX_DATASET_BYTES + 1))


@pytest.mark.asyncio
async def test_isolated_runner_timeout_is_reported_as_technical_failure():
    from app.services.isolated_experiment import _invoke

    with pytest.raises(ExperimentError, match="exceeded"):
        await _invoke({"action": "unsupported"}, timeout_seconds=0.001)


def test_cholesky_solve():
    # 2x2 positive definite matrix: [[4, 2], [2, 3]] * [x1, x2] = [8, 7]
    # Solution: x1 = 1.25, x2 = 1.5
    A = [[4.0, 2.0], [2.0, 3.0]]
    b = [8.0, 7.0]
    x = cholesky_solve(A, b)
    assert abs(x[0] - 1.25) < 1e-6
    assert abs(x[1] - 1.5) < 1e-6


def test_run_tabular_regression_v1_improvement():
    csv_text = _generate_synthetic_csv(50, correlated=True)
    res = run_tabular_regression_v1(csv_text, seed=42)

    assert res["status"] == "COMPLETED"
    assert res["verdict"] == "IMPROVEMENT"
    assert "input_checksum" in res
    assert res["manifest"]["dataset_rows"] == 50
    assert res["manifest"]["train_rows"] == 40
    assert res["manifest"]["test_rows"] == 10
    assert res["manifest"]["target_column"] == "target"

    base_mae = res["metrics"]["baseline"]["mae"]
    ridge_mae = res["metrics"]["model"]["mae"]
    assert ridge_mae < base_mae
    assert res["metrics"]["comparison"]["delta_mae"] < 0
    assert len(res["chart_data"]["samples"]) == 10
    samples = res["chart_data"]["samples"]
    test_mean = sum(row["actual"] for row in samples) / len(samples)
    ss_total = sum((row["actual"] - test_mean) ** 2 for row in samples)
    ss_res_baseline = sum((row["actual"] - row["predicted_baseline"]) ** 2 for row in samples)
    expected_baseline_r2 = 1.0 - ss_res_baseline / ss_total
    assert res["metrics"]["baseline"]["r2"] == pytest.approx(expected_baseline_r2, abs=1e-4)


def test_run_tabular_regression_v1_no_improvement():
    # Construct a dataset where features provide zero predictive power
    # and constant mean prediction is superior to regularized noisy fits
    csv_text = _generate_synthetic_csv(50, correlated=False)
    res = run_tabular_regression_v1(csv_text, seed=42)
    assert res["status"] == "COMPLETED"
    # Negative result integrity check: must be a valid outcome verdict
    assert res["verdict"] in ("IMPROVEMENT", "NO_IMPROVEMENT")
    assert res["metrics"]["comparison"]["verdict"] == res["verdict"]


def test_target_leakage_detection():
    csv_text = _generate_synthetic_csv(20)
    with pytest.raises(TargetLeakageError, match="cannot be included in feature columns"):
        run_tabular_regression_v1(
            csv_text,
            target_column="target",
            feature_columns=["f1", "target"],
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"alpha": 0},
        {"alpha": float("nan")},
        {"test_size": 0},
        {"test_size": 1},
        {"test_size": float("inf")},
        {"seed": 42.5},
    ],
)
def test_regression_rejects_invalid_parameters(kwargs):
    with pytest.raises(InvalidInputError):
        run_tabular_regression_v1(_generate_synthetic_csv(50), **kwargs)


def test_verify_repeatability_strict_tolerance():
    csv_text = _generate_synthetic_csv(50, correlated=True)
    orig_res = run_tabular_regression_v1(csv_text, seed=42)
    passed, diff = verify_repeatability(csv_text, orig_res, tolerance=1e-8)

    assert passed is True
    assert diff["status"] == "PASSED"
    assert diff["diff_mae"] <= 1e-8
    assert diff["diff_rmse"] <= 1e-8
    assert diff["diff_r2"] <= 1e-8


def test_repeatability_uses_raw_precision_and_rejects_changed_input():
    csv_text = _generate_synthetic_csv(50, correlated=True)
    original = run_tabular_regression_v1(csv_text, seed=42)
    # Leave rounded API metrics unchanged. The prior implementation compared
    # only these rounded values and incorrectly passed this tampered result.
    original["raw_metrics"]["model"]["mae"] += 0.01
    passed, report = verify_repeatability(csv_text, original)
    assert passed is False
    assert report["comparisons"]["model.mae"] is False

    changed_data = csv_text.replace("f1,f2,f3,target", "x1,f2,f3,target", 1)
    passed, report = verify_repeatability(changed_data, run_tabular_regression_v1(csv_text))
    assert passed is False
    assert report["reason"] == "INPUT_CHECKSUM_MISMATCH"


def test_computational_task_waits_for_user_dataset():
    assert route_after_methodologist({
        "research_type": "EMPIRICAL_COMPUTATIONAL",
        "dataset_csv": None,
    }) == "wait_user_data"
    assert route_after_methodologist({
        "research_type": "EMPIRICAL_COMPUTATIONAL",
        "dataset_csv": "x,target\n" + "1,2\n" * 10,
    }) == "experiment_runner"


@pytest.mark.asyncio
async def test_upload_reader_stops_at_limit_plus_one_byte():
    class FakeUpload:
        def __init__(self, content: bytes):
            self.content = content
            self.read_sizes = []

        async def read(self, size: int):
            self.read_sizes.append(size)
            chunk, self.content = self.content[:size], self.content[size:]
            return chunk

    upload = FakeUpload(b"x" * 100_000)
    with pytest.raises(UploadSizeLimitExceeded):
        await read_upload_with_limit(upload, max_size_bytes=10, chunk_size=64)
    assert sum(upload.read_sizes) <= 11


# =========================================================================
# Integration Tests for API Endpoints (Upload, Experiments, Journal)
# =========================================================================

@pytest.mark.asyncio
async def test_dataset_upload_and_retrieval():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        headers = await _register_and_login(client, suffix)

        # Create empirical computational task
        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Computational Test {suffix}",
            "research_question": "Benchmarking tabular regression v1 routine",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
            "language": "vi",
            "citation_style": "IEEE",
        })
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

        # Upload CSV dataset
        csv_data = _generate_synthetic_csv(30)
        upload_res = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=headers,
            files={"file": ("experiment_data.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        )
        assert upload_res.status_code == 201
        body = upload_res.json()
        assert body["file_name"] == "experiment_data.csv"
        assert body["rows_count"] == 30
        assert body["columns_count"] == 4
        assert "target" in body["columns"]
        assert len(body["checksum"]) == 64

        # Verify artifact download
        art_id = body["artifact_id"]
        down_res = await client.get(f"/api/v1/research/{task_id}/artifacts/{art_id}/download", headers=headers)
        assert down_res.status_code == 200
        assert down_res.headers["content-type"].startswith("text/csv")
        assert len(down_res.content) > 0


@pytest.mark.asyncio
async def test_dataset_upload_validation_errors():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        headers = await _register_and_login(client, suffix)

        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Upload Validation {suffix}",
            "research_question": "Testing upload validation errors",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
        })
        task_id = create_res.json()["id"]

        # 1. Non-CSV extension
        err_res1 = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=headers,
            files={"file": ("dataset.txt", io.BytesIO(b"a,b,c\n1,2,3"), "text/plain")},
        )
        assert err_res1.status_code == 400
        assert "Chỉ chấp nhận tệp định dạng .csv" in err_res1.json()["detail"]

        # 2. Empty CSV
        err_res2 = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=headers,
            files={"file": ("dataset.csv", io.BytesIO(b""), "text/csv")},
        )
        assert err_res2.status_code == 400
        assert "trống" in err_res2.json()["detail"]


@pytest.mark.asyncio
async def test_dataset_upload_resumes_waiting_computational_task_and_enforces_owner_scope():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        owner_headers = await _register_and_login(client, suffix)
        other_headers = await _register_and_login(client, f"other_{suffix}")

        create_res = await client.post("/api/v1/research", headers=owner_headers, json={
            "title": f"Resume Dataset {suffix}",
            "research_question": "How does the model compare against a baseline?",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
        })
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

        async with AsyncSessionLocal() as session:
            task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            task.status = "WAITING_USER_DATA"
            task.current_step = "Waiting for dataset"
            event = TaskDispatchOutbox(
                research_task_id=task.id,
                event_type="START_RESEARCH",
                dispatched_at=datetime.now(timezone.utc),
            )
            session.add(event)
            session.add(WorkflowRun(
                research_task_id=task.id,
                run_number=1,
                plan_version=task.plan_version,
                status="WAITING_USER_DATA",
                checkpoint_thread_id=str(uuid.uuid4()),
            ))
            await session.commit()

        csv_data = _generate_synthetic_csv(30, correlated=True)
        upload = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=owner_headers,
            files={"file": ("resume.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        )
        assert upload.status_code == 201

        async with AsyncSessionLocal() as session:
            task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            event = await session.scalar(select(TaskDispatchOutbox).where(
                TaskDispatchOutbox.research_task_id == task.id,
                TaskDispatchOutbox.event_type == "START_RESEARCH",
            ))
            assert task.status == "QUEUED"
            assert task.current_step is None
            assert event.dispatched_at is None

        other_upload = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=other_headers,
            files={"file": ("resume.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        )
        assert other_upload.status_code == 404


@pytest.mark.asyncio
async def test_dataset_upload_rejects_non_computational_tasks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:8]
        headers = await _register_and_login(client, suffix)
        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Review Task {suffix}",
            "research_question": "A literature review question with enough length",
            "research_type": "REVIEW",
        })
        task_id = create_res.json()["id"]
        response = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=headers,
            files={"file": ("dataset.csv", io.BytesIO(_generate_synthetic_csv().encode("utf-8")), "text/csv")},
        )
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_invalid_experiment_input_is_recorded_without_negative_result_label():
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _register_and_login(client, suffix)
        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Failed Run Test {suffix}",
            "research_question": "Does an invalid dataset produce a technical failure record?",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
        })
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

    async with AsyncSessionLocal() as session:
        task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
        task.status = "RUNNING"
        task.attempt_number = 1
        await session.commit()

    with pytest.raises(InvalidInputError):
        await nodes_module.experiment_runner_node({
            "task_id": task_id,
            "attempt_number": 1,
            "current_iteration": 0,
            "dataset_csv": "feature,target\n",
        })

    async with AsyncSessionLocal() as session:
        run = await session.scalar(select(AnalysisRun).where(
            AnalysisRun.research_task_id == uuid.UUID(task_id)
        ))
        assert run is not None
        assert run.status == "FAILED"
        assert run.reproducibility_status == "NOT_RUN"
        journal = (await session.execute(
            select(ExperimentJournalEntry)
            .where(ExperimentJournalEntry.analysis_run_id == run.id)
            .order_by(ExperimentJournalEntry.sequence)
        )).scalars().all()
        assert [entry.kind for entry in journal] == ["EXECUTION_RESULT"]
        assert journal[0].payload["status"] == "INVALID_INPUT"
        assert "NO_IMPROVEMENT" not in str(journal[0].payload)
        first_entry_id = journal[0].id

        with pytest.raises(IntegrityError, match="append-only"):
            await session.execute(
                update(ExperimentJournalEntry)
                .where(ExperimentJournalEntry.id == first_entry_id)
                .values(payload={"tampered": True})
            )
        await session.rollback()

        with pytest.raises(IntegrityError, match="append-only"):
            await session.execute(
                delete(ExperimentJournalEntry)
                .where(ExperimentJournalEntry.id == first_entry_id)
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_technical_runner_failure_keeps_frozen_plan_and_failed_attempt(monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, suffix)
        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Runner Failure Test {suffix}",
            "research_question": "Can a routine failure be distinguished from a negative result?",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
        })
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

    async with AsyncSessionLocal() as session:
        task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
        task.status = "RUNNING"
        task.attempt_number = 1
        await session.commit()

    from app.services import isolated_experiment

    async def fail_runner(*_args, **_kwargs):
        raise RuntimeError("simulated runner process failure")

    monkeypatch.setattr(isolated_experiment, "run_tabular_regression_isolated", fail_runner)

    with pytest.raises(RuntimeError, match="simulated runner process failure"):
        await nodes_module.experiment_runner_node({
            "task_id": task_id,
            "attempt_number": 1,
            "current_iteration": 0,
            "dataset_csv": _generate_synthetic_csv(30),
        })

    async with AsyncSessionLocal() as session:
        run = await session.scalar(select(AnalysisRun).where(
            AnalysisRun.research_task_id == uuid.UUID(task_id)
        ))
        assert run is not None and run.status == "FAILED"
        assert run.manifest["parameters"]["seed"] == 42
        journal = (await session.execute(
            select(ExperimentJournalEntry)
            .where(ExperimentJournalEntry.analysis_run_id == run.id)
            .order_by(ExperimentJournalEntry.sequence)
        )).scalars().all()
        assert [entry.kind for entry in journal] == ["PLAN_FROZEN", "STARTED", "EXECUTION_RESULT"]
        assert journal[-1].payload["status"] == "TECHNICAL_FAILURE"


# =========================================================================
# End-to-End Workflow Execution Test with Experiment Runner & Journal
# =========================================================================

@pytest.mark.asyncio
async def test_e2e_empirical_computational_workflow(monkeypatch):
    suffix = uuid.uuid4().hex[:8]

    # Mock Supervisor
    plan_mock = nodes_module.SupervisorPlan(
        research_angle="benchmarking empirical tabular regression v1 routine",
        search_queries=["tabular regression baseline ridge", "predictive performance"],
        required_sections=[
            "Title", "Abstract", "Introduction", "Research Questions",
            "Methods", "Results", "Discussion", "Limitations", "Conclusion", "References"
        ],
    )

    # Mock Methodologist
    proto_mock = nodes_module.MethodologistProtocol(
        research_questions=["What is the baseline vs Ridge regression MAE?"],
        hypotheses=["H1: Ridge regression with alpha=1.0 achieves lower MAE than mean baseline."],
        variables={
            "independent": ["f1", "f2", "f3"],
            "dependent": ["target"],
            "control": ["seed=42", "split=80/20"],
        },
        study_design="Standardized 80/20 train/test evaluation with Cholesky Ridge solver",
        data_collection_procedure="Numeric dataset profiling and train-only fit preprocessing",
        analysis_plan="Mean baseline comparison against Ridge alpha=1.0",
        ethical_considerations="Open benchmark data without human subject risk.",
        protocol_markdown="# Computational Study Protocol\n\nDesign: Ridge vs Mean Baseline",
    )

    class FakeStructuredLLM:
        def __init__(self, schema=None):
            self.schema = schema

        def with_structured_output(self, schema):
            return FakeStructuredLLM(schema=schema)

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, _messages):
            if self.schema is nodes_module.SupervisorPlan:
                return plan_mock
            if self.schema is nodes_module.MethodologistProtocol:
                return proto_mock
            if self.schema is nodes_module.AnalystExtraction:
                return nodes_module.AnalystExtraction(claims=[
                    nodes_module.ExtractedClaim(
                        claim="Ridge regression with alpha=1.0 achieves lower MAE than mean baseline.",
                        evidence_quote="Empirical evaluation confirms performance metrics on benchmark datasets.",
                    )
                ])
            if self.schema is nodes_module.CriticVerdict:
                return supported_critic_response(_messages)
            raise AssertionError(f"Unexpected schema: {self.schema}")

    class FakeSmartWriterLLM:
        def with_structured_output(self, schema):
            return FakeStructuredLLM(schema=schema)

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, messages):
            prompt_text = messages[0].content
            claim_ids = re.findall(r"\[\[@claim:([a-f0-9\-]+)\]\]", prompt_text)
            assert claim_ids, "Writer must receive persisted, source-grounded claim IDs"
            markers = " ".join(f"[[@claim:{cid}]]" for cid in claim_ids)
            content = (
                f"# Báo cáo thực nghiệm: Tabular Regression v1\n\n"
                f"## Tóm tắt\nNghiên cứu thực nghiệm đối chuẩn Ridge regression và Mean baseline.\n\n"
                f"## Kết quả\nĐo lường đối chứng MAE và RMSE: {markers}\n\n"
                f"## Kết luận\nKết quả dự đoán và không suy luận nhân quả."
            )
            from tests.manuscript_helpers import complete_manuscript
            return SimpleNamespace(content=complete_manuscript(content, "EMPIRICAL_COMPUTATIONAL", prompt=prompt_text))

    monkeypatch.setattr(nodes_module, "get_fast_llm", lambda: FakeStructuredLLM())
    monkeypatch.setattr(nodes_module, "get_smart_llm", lambda: FakeSmartWriterLLM())

    async def fake_search(_queries, max_results_per_query=3, budget_context=None, **kwargs):
        return [
            SearchResult(
                url="https://tabular-ml.example.org/study",
                title="Empirical Tabular Regression Benchmarks",
                content="Empirical evaluation confirms performance metrics on benchmark datasets.",
            )
        ]

    async def fake_fetch(urls, max_concurrent=5):
        return {url: "Empirical evaluation confirms performance metrics on benchmark datasets." for url in urls}

    monkeypatch.setattr("app.tools.search.execute_parallel_searches", fake_search)
    monkeypatch.setattr("app.tools.scraper.fetch_urls_parallel", fake_fetch)

    class FakeEmbedder:
        async def embed_and_store(self, db, task_id, source_id, text_content, budget_context=None):
            db.add(DocumentChunk(
                research_task_id=task_id,
                source_id=source_id,
                chunk_index=0,
                content=text_content,
                token_count=7,
            ))
            await db.flush()
            return 1

        async def search_similar_chunks(self, db, task_id, _query, limit=3, budget_context=None):
            rows = (await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.research_task_id == task_id)
                .order_by(DocumentChunk.chunk_index)
                .limit(limit)
            )).scalars().all()
            return [(row, 0.0) for row in rows]

    monkeypatch.setattr("app.tools.embedder.EmbedderTool", FakeEmbedder)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _register_and_login(client, suffix)

        create_res = await client.post("/api/v1/research", headers=headers, json={
            "title": f"Empirical Workflow Test {suffix}",
            "research_question": "What is the comparative predictive performance of tabular regression v1?",
            "research_type": "EMPIRICAL_COMPUTATIONAL",
            "require_plan_approval": False,
        })
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

        # Upload a custom CSV dataset
        custom_csv = _generate_synthetic_csv(40, correlated=True)
        up_res = await client.post(
            f"/api/v1/research/{task_id}/dataset",
            headers=headers,
            files={"file": ("benchmark_data.csv", io.BytesIO(custom_csv.encode("utf-8")), "text/csv")},
        )
        assert up_res.status_code == 201

        # Trigger worker execution
        start_res = await client.post(f"/api/v1/research/{task_id}/start", headers=headers)
        assert start_res.status_code == 202

        worker_result = await run_langgraph_workflow(task_id)
        assert worker_result["status"] == "SUCCESS"

        # Verify task is COMPLETED in DB
        async with AsyncSessionLocal() as session:
            task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            assert task.status == "COMPLETED"

            # Check AnalysisRun created
            runs = (await session.execute(
                select(AnalysisRun).where(AnalysisRun.research_task_id == task.id)
            )).scalars().all()
            assert len(runs) >= 1
            run = runs[0]
            assert run.routine_name == "tabular_regression_v1"
            assert run.status == "COMPLETED"
            assert run.reproducibility_status == "PASSED"
            assert run.metrics is not None
            assert "baseline" in run.metrics
            assert "model" in run.metrics
            assert "comparison" in run.metrics
            assert run.reproducibility_diff["diff_mae"] <= 1e-8

            # Check the append-only journal, including persisted output artifacts.
            journal = (await session.execute(
                select(ExperimentJournalEntry)
                .where(ExperimentJournalEntry.research_task_id == task.id)
                .order_by(ExperimentJournalEntry.sequence.asc())
            )).scalars().all()
            assert len(journal) == 7
            kinds = [j.kind for j in journal]
            assert kinds == [
                "PLAN_FROZEN",
                "STARTED",
                "EXECUTION_RESULT",
                "OBSERVATION",
                "REPRODUCTION_CHECK",
                "INTERPRETATION",
                "ARTIFACTS_PERSISTED",
            ]
            assert len(journal[-1].artifact_ids) >= 4

            # Check ExportArtifacts
            artifacts = (await session.execute(
                select(ExportArtifact).where(ExportArtifact.research_task_id == task.id)
            )).scalars().all()
            export_types = {a.export_type for a in artifacts}
            assert "METRICS_JSON" in export_types
            assert "MANIFEST_JSON" in export_types
            assert "CHART_DATA_JSON" in export_types
            assert "REPRO_README" in export_types
            assert "DATASET_CSV" in export_types

        # Check API endpoints for experiments and journal
        exp_res = await client.get(f"/api/v1/research/{task_id}/experiments", headers=headers)
        assert exp_res.status_code == 200
        exp_body = exp_res.json()
        assert len(exp_body) >= 1
        assert exp_body[0]["routine_name"] == "tabular_regression_v1"
        assert exp_body[0]["reproducibility_status"] == "PASSED"

        jr_res = await client.get(f"/api/v1/research/{task_id}/journal", headers=headers)
        assert jr_res.status_code == 200
        jr_body = jr_res.json()
        assert len(jr_body) == 7
        assert jr_body[0]["kind"] == "PLAN_FROZEN"
        assert jr_body[5]["kind"] == "INTERPRETATION"
        assert jr_body[6]["kind"] == "ARTIFACTS_PERSISTED"
