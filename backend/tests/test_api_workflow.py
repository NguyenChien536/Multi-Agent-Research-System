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
from app.models.report import ResearchReport
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.worker import run_langgraph_workflow


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
            await db.commit()
        assert await task_dispatcher.recover_expired_worker_claims() == 1
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

        report = await client.get(f"/api/v1/research/{author_id}/report", headers=author_headers)
        assert report.status_code == 200, report.text
        assert report.json()["research_task_id"] == author_id
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

        # Delete endpoint
        # Reader cannot delete author's task
        assert (await client.delete(f"/api/v1/research/{cancel_id}", headers=reader_headers)).status_code == 404

        # Author can delete task
        delete_res = await client.delete(f"/api/v1/research/{cancel_id}", headers=author_headers)
        assert delete_res.status_code == 200
        assert (await client.get(f"/api/v1/research/{cancel_id}", headers=author_headers)).status_code == 404

    # pytest-asyncio gives each test a new loop; pooled asyncpg connections
    # cannot be reused by the next test's loop.
    await engine.dispose()

