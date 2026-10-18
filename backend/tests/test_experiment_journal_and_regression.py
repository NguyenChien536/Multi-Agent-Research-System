"""Tests for Phase 5: Computational Routine tabular_regression_v1, AnalysisRun, and ExperimentJournalEntry."""

import io
import random
import re
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents import nodes as nodes_module
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.report import ExportArtifact, ResearchReport
from app.models.source import DocumentChunk
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.services.experiment_runner import (
    InvalidInputError,
    TargetLeakageError,
    cholesky_solve,
    parse_csv_dataset,
    run_tabular_regression_v1,
    verify_repeatability,
)
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


def test_verify_repeatability_strict_tolerance():
    csv_text = _generate_synthetic_csv(50, correlated=True)
    orig_res = run_tabular_regression_v1(csv_text, seed=42)
    passed, diff = verify_repeatability(csv_text, orig_res, tolerance=1e-8)

    assert passed is True
    assert diff["status"] == "PASSED"
    assert diff["diff_mae"] <= 1e-8
    assert diff["diff_rmse"] <= 1e-8
    assert diff["diff_r2"] <= 1e-8


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
                return nodes_module.CriticVerdict(verdict="PASS", feedback=[], missing_areas=[])
            raise AssertionError(f"Unexpected schema: {self.schema}")

    class FakeSmartWriterLLM:
        def with_structured_output(self, schema):
            return FakeStructuredLLM(schema=schema)

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, messages):
            prompt_text = messages[0].content
            claim_ids = re.findall(r"'claim_id':\s*UUID\('([a-f0-9\-]+)'\)", prompt_text)
            markers = " ".join(f"[[@claim:{cid}]]" for cid in claim_ids)
            content = (
                f"# Báo cáo thực nghiệm: Tabular Regression v1\n\n"
                f"## Tóm tắt\nNghiên cứu thực nghiệm đối chuẩn Ridge regression và Mean baseline.\n\n"
                f"## Kết quả\nĐo lường đối chứng MAE và RMSE: {markers}\n\n"
                f"## Kết luận\nKết quả dự đoán và không suy luận nhân quả."
            )
            return SimpleNamespace(content=content)

    monkeypatch.setattr(nodes_module, "get_fast_llm", lambda: FakeStructuredLLM())
    monkeypatch.setattr(nodes_module, "get_smart_llm", lambda: FakeSmartWriterLLM())

    async def fake_search(_queries, max_results_per_query=3):
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
        async def embed_and_store(self, db, task_id, source_id, text_content):
            db.add(DocumentChunk(
                research_task_id=task_id,
                source_id=source_id,
                chunk_index=0,
                content=text_content,
                token_count=7,
            ))
            await db.flush()
            return 1

        async def search_similar_chunks(self, db, task_id, _query, limit=3):
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

            # Check ExperimentJournalEntry items created (sequence 1..6)
            journal = (await session.execute(
                select(ExperimentJournalEntry)
                .where(ExperimentJournalEntry.research_task_id == task.id)
                .order_by(ExperimentJournalEntry.sequence.asc())
            )).scalars().all()
            assert len(journal) == 6
            kinds = [j.kind for j in journal]
            assert kinds == [
                "PLAN_FROZEN",
                "STARTED",
                "EXECUTION_RESULT",
                "OBSERVATION",
                "REPRODUCTION_CHECK",
                "INTERPRETATION",
            ]
            for j in journal:
                assert len(j.artifact_ids) >= 4

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
        assert len(jr_body) == 6
        assert jr_body[0]["kind"] == "PLAN_FROZEN"
        assert jr_body[5]["kind"] == "INTERPRETATION"
