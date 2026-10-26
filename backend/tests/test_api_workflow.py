"""API integration checks against an isolated PostgreSQL database.

CI migrates a fresh database before running this module. No Celery worker or
external AI provider is contacted.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.services import task_dispatcher
from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.report import ResearchReport, ReportVersion
from app.models.task import ResearchTask, TaskDispatchOutbox, TaskDeletionOutbox
from app.worker import run_langgraph_workflow, run_task_deletion


@pytest.mark.asyncio
async def test_auth_and_research_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched: list[str] = []
    should_fail_dispatch = True

    def publish(task_id: str) -> None:
        if should_fail_dispatch:
            raise ConnectionError("broker unavailable")
        dispatched.append(task_id)

    monkeypatch.setattr(task_dispatcher, "execute_research_workflow", SimpleNamespace(delay=publish))

    suffix = uuid.uuid4().hex[:12]
    users = [
        {"username": f"author_{suffix}", "email": f"author_{suffix}@example.com", "password": "SecurePass123!"},
        {"username": f"reader_{suffix}", "email": f"reader_{suffix}@example.com", "password": "SecurePass123!"},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/research")).status_code == 401
        assert (await client.post("/api/v1/research", json={
            "title": "Unauthenticated task",
            "research_question": "Should reject without a token?",
        })).status_code == 401

        tokens = []
        for user in users:
            registered = await client.post("/api/v1/auth/register", json=user)
            assert registered.status_code == 201, registered.text
            logged_in = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": user["password"]},
            )
            assert logged_in.status_code == 200, logged_in.text
            tokens.append(logged_in.json()["access_token"])

        author_headers = {"Authorization": f"Bearer {tokens[0]}"}
        reader_headers = {"Authorization": f"Bearer {tokens[1]}"}
        assert (await client.get("/api/v1/auth/me", headers=author_headers)).json()["email"] == users[0]["email"]
        assert (await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})).status_code == 401
        assert (await client.post(
            "/api/v1/auth/login",
            json={"email": users[0]["email"], "password": "wrong-password"},
        )).status_code == 401

        payload = {
            "title": "Research task for ownership check",
            "research_question": "How can evidence be traced to a research report?",
            "research_depth": "STANDARD",
        }
        author_task = await client.post("/api/v1/research", json=payload, headers=author_headers)
        reader_task = await client.post("/api/v1/research", json=payload, headers=reader_headers)
        assert author_task.status_code == 201, author_task.text
        assert reader_task.status_code == 201, reader_task.text
        author_id = author_task.json()["id"]
        reader_id = reader_task.json()["id"]
        assert author_task.json()["user_id"] != reader_task.json()["user_id"]

        author_list = await client.get("/api/v1/research", headers=author_headers)
        reader_list = await client.get("/api/v1/research", headers=reader_headers)
        assert author_list.status_code == reader_list.status_code == 200
        assert author_id in {item["id"] for item in author_list.json()}
        assert reader_id not in {item["id"] for item in author_list.json()}
        assert reader_id in {item["id"] for item in reader_list.json()}
        assert author_id not in {item["id"] for item in reader_list.json()}

        assert (await client.get(f"/api/v1/research/{author_id}", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{author_id}")).status_code == 401
        assert (await client.post(f"/api/v1/research/{author_id}/start", headers=reader_headers)).status_code == 404
        assert (await client.post(f"/api/v1/research/{author_id}/start")).status_code == 401
        assert (await client.get(f"/api/v1/research/{author_id}/report", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{author_id}/report")).status_code == 401

        started = await client.post(f"/api/v1/research/{author_id}/start", headers=author_headers)
        assert started.status_code == 202, started.text
        assert started.json()["status"] == "QUEUED"
        assert (await client.post(f"/api/v1/research/{author_id}/start", headers=author_headers)).status_code == 409

        # A broker outage leaves the durable event retryable; recovery publishes it.
        assert await task_dispatcher.dispatch_one_outbox_event()
        async with AsyncSessionLocal() as db:
            event = (await db.execute(
                select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id == uuid.UUID(author_id))
            )).scalar_one()
            assert event.dispatched_at is None
            assert event.attempts == 1
            assert "broker unavailable" in event.last_error
            event.available_at = datetime.now(timezone.utc)
            await db.commit()
        should_fail_dispatch = False
        assert await task_dispatcher.dispatch_one_outbox_event()
        assert dispatched == [author_id]

        # A lost worker stops renewing its lease; recovery requeues the same task.
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, uuid.UUID(author_id))
            task.status = "RUNNING"
            task.attempt_number = 1
            task.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            analysis_run = AnalysisRun(
                research_task_id=task.id,
                routine_name="tabular_regression_v1",
                status="STARTED",
                manifest={"routine_name": "tabular_regression_v1"},
            )
            db.add(analysis_run)
            await db.flush()
            db.add_all([
                ExperimentJournalEntry(
                    research_task_id=task.id,
                    analysis_run_id=analysis_run.id,
                    sequence=1,
                    kind="PLAN_FROZEN",
                    actor="METHODOLOGIST",
                ),
                ExperimentJournalEntry(
                    research_task_id=task.id,
                    analysis_run_id=analysis_run.id,
                    sequence=2,
                    kind="STARTED",
                    actor="SYSTEM",
                ),
            ])
            await db.commit()
        assert await task_dispatcher.recover_expired_worker_claims() == 1
        async with AsyncSessionLocal() as db:
            recovered_run = await db.get(AnalysisRun, analysis_run.id)
            assert recovered_run.status == "FAILED"
            assert "lease expired" in recovered_run.error_message
            failed_attempt = (await db.execute(
                select(ExperimentJournalEntry).where(
                    ExperimentJournalEntry.analysis_run_id == analysis_run.id,
                    ExperimentJournalEntry.sequence == 3,
                )
            )).scalar_one()
            assert failed_attempt.payload["status"] == "TECHNICAL_FAILURE"
            assert failed_attempt.payload["error_type"] == "WORKER_LEASE_EXPIRED"
        assert await task_dispatcher.dispatch_one_outbox_event()
        assert dispatched == [author_id, author_id]

        class SuccessfulGraph:
            async def ainvoke(self, _state: dict) -> dict:
                return {"final_report_markdown": "# Evidence report", "current_agent": "Writer"}

        monkeypatch.setattr("app.worker.research_graph", SuccessfulGraph())
        assert (await run_langgraph_workflow(author_id))["status"] == "SUCCESS"
        assert (await run_langgraph_workflow(author_id))["status"] == "IGNORED"

        async with AsyncSessionLocal() as db:
            reports = (await db.execute(
                select(ResearchReport).where(ResearchReport.research_task_id == uuid.UUID(author_id))
            )).scalars().all()
            assert len(reports) == 1
            report_versions = (await db.execute(
                select(ReportVersion).where(ReportVersion.report_id == reports[0].id)
            )).scalars().all()
            assert len(report_versions) == 1
            assert report_versions[0].version_number == 1
            assert report_versions[0].workflow_run_id is not None

        report = await client.get(f"/api/v1/research/{author_id}/report", headers=author_headers)
        assert report.status_code == 200, report.text
        assert report.json()["research_task_id"] == author_id
        assert report.json()["version_number"] == 1
        assert (await client.get(f"/api/v1/research/{author_id}/report", headers=reader_headers)).status_code == 404

        citations = await client.get(f"/api/v1/research/{author_id}/citations", headers=author_headers)
        assert citations.status_code == 200, citations.text
        assert isinstance(citations.json(), list)
        assert (await client.get(f"/api/v1/research/{author_id}/citations", headers=reader_headers)).status_code == 404

        # Sources endpoint
        sources = await client.get(f"/api/v1/research/{author_id}/sources", headers=author_headers)
        assert sources.status_code == 200, sources.text
        assert isinstance(sources.json(), list)
        assert (await client.get(f"/api/v1/research/{author_id}/sources", headers=reader_headers)).status_code == 404

        # Agent Runs endpoint
        runs = await client.get(f"/api/v1/research/{author_id}/agent-runs", headers=author_headers)
        assert runs.status_code == 200, runs.text
        assert isinstance(runs.json(), list)
        assert (await client.get(f"/api/v1/research/{author_id}/agent-runs", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{author_id}/agent-runs")).status_code == 401

        # Cancel endpoint
        new_task = await client.post("/api/v1/research", json={
            "title": "Task to be cancelled",
            "research_question": "Can this task be cancelled safely?",
        }, headers=author_headers)
        assert new_task.status_code == 201
        cancel_id = new_task.json()["id"]

        # Reader cannot cancel author's task
        assert (await client.post(f"/api/v1/research/{cancel_id}/cancel", headers=reader_headers)).status_code == 404

        # Author can cancel task
        cancel_res = await client.post(f"/api/v1/research/{cancel_id}/cancel", headers=author_headers)
        assert cancel_res.status_code == 200, cancel_res.text
        assert cancel_res.json()["status"] == "CANCELLED"

        # Idempotent cancel
        cancel_res2 = await client.post(f"/api/v1/research/{cancel_id}/cancel", headers=author_headers)
        assert cancel_res2.status_code == 200
        assert cancel_res2.json()["status"] == "CANCELLED"

        # Restart CANCELLED task
        restart_res = await client.post(f"/api/v1/research/{cancel_id}/start", headers=author_headers)
        assert restart_res.status_code == 202, restart_res.text
        assert restart_res.json()["status"] == "QUEUED"

        # Re-cancel before deleting
        await client.post(f"/api/v1/research/{cancel_id}/cancel", headers=author_headers)


        # Delete endpoint
        # Reader cannot delete author's task
        assert (await client.delete(f"/api/v1/research/{cancel_id}", headers=reader_headers)).status_code == 404

        # Author can delete task
        # Author can delete task
        delete_res = await client.delete(f"/api/v1/research/{cancel_id}", headers=author_headers)
        assert delete_res.status_code == 202
        assert delete_res.json()["status"] == "DELETING"
        assert (await client.get(f"/api/v1/research/{cancel_id}", headers=author_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/research/{cancel_id}", headers=author_headers)).status_code == 202
        listed_after_delete = await client.get("/api/v1/research", headers=author_headers)
        assert cancel_id not in {item["id"] for item in listed_after_delete.json()}
        deletion_jobs: list[str] = []
        monkeypatch.setattr(
            task_dispatcher.execute_task_deletion,
            "delay",
            lambda task_id: deletion_jobs.append(task_id),
        )
        assert await task_dispatcher.dispatch_one_task_deletion_event()
        assert deletion_jobs == [cancel_id]

        async with AsyncSessionLocal() as db:
            deleted_task = await db.get(ResearchTask, uuid.UUID(cancel_id))
            assert deleted_task is not None and deleted_task.status == "DELETING"
            await db.commit()
            assert await db.scalar(
                select(TaskDeletionOutbox.id).where(TaskDeletionOutbox.research_task_id == uuid.UUID(cancel_id))
            ) is not None
            deletion_event = await db.scalar(
                select(TaskDeletionOutbox).where(TaskDeletionOutbox.research_task_id == uuid.UUID(cancel_id))
            )
            deletion_event.cleanup_lease_until = datetime.now(timezone.utc) + timedelta(minutes=1)
            await db.commit()
        assert (await run_task_deletion(cancel_id))["status"] == "ALREADY_CLAIMED"
        async with AsyncSessionLocal() as db:
            deletion_event = await db.scalar(
                select(TaskDeletionOutbox).where(TaskDeletionOutbox.research_task_id == uuid.UUID(cancel_id))
            )
            deletion_event.cleanup_lease_until = None
            await db.commit()

        import app.services.artifact_store as artifact_store_module
        original_cleanup = artifact_store_module.artifact_store.delete_task_artifacts
        monkeypatch.setattr(
            artifact_store_module.artifact_store,
            "delete_task_artifacts",
            lambda _task_id: (_ for _ in ()).throw(OSError("disk unavailable")),
        )
        cleanup_failed = await run_task_deletion(cancel_id)
        assert cleanup_failed["status"] == "RETRY"
        async with AsyncSessionLocal() as db:
            pending_cleanup = await db.scalar(
                select(TaskDeletionOutbox).where(TaskDeletionOutbox.research_task_id == uuid.UUID(cancel_id))
            )
            assert pending_cleanup is not None
            assert "disk unavailable" in pending_cleanup.last_error

        monkeypatch.setattr(artifact_store_module.artifact_store, "delete_task_artifacts", original_cleanup)

        async with AsyncSessionLocal() as db:
            deleted_task = await db.get(ResearchTask, uuid.UUID(cancel_id))
            assert deleted_task is not None
            deleted_task.worker_lease_until = datetime.now(timezone.utc) + timedelta(minutes=1)
            await db.commit()

        deferred = await run_task_deletion(cancel_id)
        assert deferred["status"] == "DEFERRED"
        async with AsyncSessionLocal() as db:
            deleted_task = await db.get(ResearchTask, uuid.UUID(cancel_id))
            assert deleted_task is not None and deleted_task.status == "DELETING"
            deleted_task.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()

        cleaned = await run_task_deletion(cancel_id)
        assert cleaned["status"] == "DELETED"
        async with AsyncSessionLocal() as db:
            assert await db.get(ResearchTask, uuid.UUID(cancel_id)) is None

    # pytest-asyncio gives each test a new loop; pooled asyncpg connections
    # cannot be reused by the next test's loop.
    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_run_persistence_and_cost_accounting(monkeypatch):
    """Verify that agent run metadata is accurately persisted, tokens counted, cost calculated, and task totals reconciled."""
    from app.services.agent_run import estimate_cost, extract_tokens, get_active_model_name, record_agent_run
    from app.models.agent_run import AgentRun
    from app.worker import run_langgraph_workflow

    # 1. Test cost estimation helper
    cost_lite = estimate_cost("gemini-3.5-flash-lite", 10000, 2000)
    assert cost_lite > 0
    cost_smart = estimate_cost("gemini-3.5-flash", 10000, 2000)
    assert cost_smart > cost_lite

    # 2. Test token extraction
    in_tok, out_tok = extract_tokens(None, prompt_str="Hello world test", output_str="Output response")
    assert in_tok >= 1
    assert out_tok >= 1

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", async_session)

    suffix = uuid.uuid4().hex[:8]
    user_cred = {
        "username": f"cost_tracker_{suffix}",
        "email": f"cost_tracker_{suffix}@example.com",
        "password": "SecurePassword123!",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg_res = await client.post("/api/v1/auth/register", json=user_cred)
        assert reg_res.status_code == 201, reg_res.text
        login_res = await client.post("/api/v1/auth/login", json={"email": user_cred["email"], "password": user_cred["password"]})
        assert login_res.status_code == 200, login_res.text
        token = login_res.json()["access_token"]
        author_headers = {"Authorization": f"Bearer {token}"}
        # Create research task
        task_res = await client.post("/api/v1/research", json={
            "title": "Cost & Agent Run Accounting Test",
            "research_question": "How are LLM tokens and costs reconciled across multiple agents?",
        }, headers=author_headers)
        assert task_res.status_code == 201
        task_id = task_res.json()["id"]

        # Record individual agent runs directly
        run1_id = await record_agent_run(
            task_id=task_id,
            agent_name="Supervisor",
            status="SUCCESS",
            iteration=0,
            attempt_number=1,
            model="gemini-3.5-flash-lite",
            duration_ms=450,
            input_tokens=1500,
            output_tokens=300,
            estimated_cost=0.000203,
            input_summary={"question": "sample"},
            output_summary={"queries_count": 3},
        )
        assert run1_id is not None

        run2_id = await record_agent_run(
            task_id=task_id,
            agent_name="Writer",
            status="SUCCESS",
            iteration=0,
            attempt_number=1,
            model="gemini-3.5-flash",
            duration_ms=1200,
            input_tokens=3500,
            output_tokens=1200,
            estimated_cost=0.001245,
            input_summary={"claims_count": 5},
            output_summary={"draft_words": 650},
        )
        assert run2_id is not None

        # Fetch runs via API
        api_runs = await client.get(f"/api/v1/research/{task_id}/agent-runs", headers=author_headers)
        assert api_runs.status_code == 200
        runs_data = api_runs.json()
        assert len(runs_data) == 2
        assert runs_data[0]["agent_name"] == "Supervisor"
        assert runs_data[0]["input_tokens"] == 1500
        assert runs_data[1]["agent_name"] == "Writer"
        assert runs_data[1]["output_tokens"] == 1200

        # Start task and run workflow to test reconciliation
        start_res = await client.post(f"/api/v1/research/{task_id}/start", headers=author_headers)
        assert start_res.status_code == 202

        class MockCompletedGraph:
            async def ainvoke(self, _state: dict) -> dict:
                return {"final_report_markdown": "# Reconciled Report\n\nContent here.", "current_agent": "Writer"}

        monkeypatch.setattr("app.worker.research_graph", MockCompletedGraph())
        workflow_res = await run_langgraph_workflow(task_id)
        assert workflow_res["status"] == "SUCCESS"

        # Verify task completed_at, total_tokens_used, and total_cost_usd
        updated_task = await client.get(f"/api/v1/research/{task_id}", headers=author_headers)
        assert updated_task.status_code == 200
        data = updated_task.json()
        assert data["status"] == "COMPLETED"
        assert data["completed_at"] is not None
        assert data["total_tokens_used"] == (1500 + 300 + 3500 + 1200)
        assert data["total_cost_usd"] > 0

    await engine.dispose()


