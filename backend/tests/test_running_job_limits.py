"""Focused tests for per-user concurrent running job limits (Issue #15).

Verifies:
1. Atomic capacity admission under racing claims (max 2 RUNNING per user).
2. Overflow tasks remain durably QUEUED.
3. Queue progression after task completion and after task failure.
4. Independent capacity per user (one user at limit does not block another).
5. Non-running states (QUEUED, WAITING_*) do not consume running slots.
6. Duplicate delivery protection and worker lease recovery.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.services import task_dispatcher
from app.worker import run_langgraph_workflow


class ControllableGraph:
    def __init__(self, pause_event: asyncio.Event | None = None, fail: bool = False):
        self.pause_event = pause_event
        self.fail = fail

    async def ainvoke(self, _state: dict) -> dict:
        if self.pause_event is not None:
            await self.pause_event.wait()
        if self.fail:
            raise RuntimeError("Simulated failure in research workflow")
        return {"final_report_markdown": "# Completed Report", "current_agent": "Writer"}


async def create_and_start_task(client: AsyncClient, headers: dict, title: str) -> str:
    created = await client.post(
        "/api/v1/research",
        headers=headers,
        json={"title": title, "research_question": f"Question for {title}", "research_depth": "STANDARD"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    started = await client.post(f"/api/v1/research/{task_id}/start", headers=headers)
    assert started.status_code == 202, started.text
    return task_id


async def register_user(client: AsyncClient, username: str) -> dict:
    email = f"{username}@example.com"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "SecurePassword123!"},
    )
    assert registered.status_code == 201, registered.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_atomic_per_user_admission_under_racing_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched_ids: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: dispatched_ids.append(task_id)),
    )

    pause_gate = asyncio.Event()
    controllable_graph = ControllableGraph(pause_event=pause_gate)
    monkeypatch.setattr("app.worker.research_graph", controllable_graph)

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await register_user(client, f"racing_{suffix}")

        t1 = await create_and_start_task(client, headers, "Task 1")
        t2 = await create_and_start_task(client, headers, "Task 2")
        t3 = await create_and_start_task(client, headers, "Task 3")

        # 3 workers race to claim queued tasks for the same user simultaneously.
        w1 = asyncio.create_task(run_langgraph_workflow(t1))
        w2 = asyncio.create_task(run_langgraph_workflow(t2))
        w3 = asyncio.create_task(run_langgraph_workflow(t3))

        # Give them time to attempt claiming in the DB
        await asyncio.sleep(0.1)

        # In DB, verify only 2 are RUNNING and 1 is QUEUED
        async with AsyncSessionLocal() as db:
            tasks = (await db.execute(select(ResearchTask).where(ResearchTask.id.in_([uuid.UUID(t1), uuid.UUID(t2), uuid.UUID(t3)])))).scalars().all()
            status_counts = {}
            for t in tasks:
                status_counts[t.status] = status_counts.get(t.status, 0) + 1
            assert status_counts == {"RUNNING": 2, "QUEUED": 1}

            rejected_task = next(t for t in tasks if t.status == "QUEUED")
            rejected_task_id = str(rejected_task.id)
            assert rejected_task.attempt_number == 0

        # Release the active tasks so they can finish execution
        pause_gate.set()
        results = await asyncio.gather(w1, w2, w3)

        # Exactly 2 should have completed successfully; 1 returned QUEUED
        queued_results = [r for r in results if r.get("status") == "QUEUED"]
        assert len(queued_results) == 1
        assert queued_results[0]["task_id"] == rejected_task_id
        assert "limit" in queued_results[0]["message"].lower()
        await asyncio.sleep(0.05)

        # After active tasks completed, the rejected task should have been dispatched automatically
        assert rejected_task_id in dispatched_ids

        # The previously queued task can now claim and run successfully
        t3_result = await run_langgraph_workflow(rejected_task_id)
        assert t3_result["status"] == "SUCCESS"

        async with AsyncSessionLocal() as db:
            t3_db = await db.get(ResearchTask, uuid.UUID(rejected_task_id))
            assert t3_db.status == "COMPLETED"

    await engine.dispose()


@pytest.mark.asyncio
async def test_separate_users_independent_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched_ids: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: dispatched_ids.append(task_id)),
    )

    pause_gate = asyncio.Event()
    controllable_graph = ControllableGraph(pause_event=pause_gate)
    monkeypatch.setattr("app.worker.research_graph", controllable_graph)

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_a_headers = await register_user(client, f"usera_{suffix}")
        user_b_headers = await register_user(client, f"userb_{suffix}")

        # User A starts 2 tasks (reaches max capacity 2)
        ua_t1 = await create_and_start_task(client, user_a_headers, "User A Task 1")
        ua_t2 = await create_and_start_task(client, user_a_headers, "User A Task 2")

        # Worker claims User A's tasks
        claim_a1 = asyncio.create_task(run_langgraph_workflow(ua_t1))
        claim_a2 = asyncio.create_task(run_langgraph_workflow(ua_t2))
        await asyncio.sleep(0.05)

        # Verify User A has 2 running tasks
        async with AsyncSessionLocal() as db:
            t1_db = await db.get(ResearchTask, uuid.UUID(ua_t1))
            t2_db = await db.get(ResearchTask, uuid.UUID(ua_t2))
            assert t1_db.status == "RUNNING"
            assert t2_db.status == "RUNNING"

        # User B starts a task: User B must NOT be blocked by User A's running tasks
        ub_t1 = await create_and_start_task(client, user_b_headers, "User B Task 1")
        ub_claim = asyncio.create_task(run_langgraph_workflow(ub_t1))
        await asyncio.sleep(0.05)

        async with AsyncSessionLocal() as db:
            tb1_db = await db.get(ResearchTask, uuid.UUID(ub_t1))
            assert tb1_db.status == "RUNNING"

        # Release all running tasks
        pause_gate.set()
        res_a1 = await claim_a1
        res_a2 = await claim_a2
        res_b1 = await ub_claim
        assert res_a1["status"] == "SUCCESS"
        assert res_a2["status"] == "SUCCESS"
        assert res_b1["status"] == "SUCCESS"

    await engine.dispose()


@pytest.mark.asyncio
async def test_queue_progression_after_task_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched_ids: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: dispatched_ids.append(task_id)),
    )

    # Task 1 will fail deliberately; Task 2 will run normally
    fail_graph = ControllableGraph(fail=True)
    normal_graph = ControllableGraph(fail=False)

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Use limit=1 to clearly test progression on failure
        monkeypatch.setattr(settings, "MAX_CONCURRENT_TASKS_PER_USER", 1)

        headers = await register_user(client, f"failtest_{suffix}")
        t1 = await create_and_start_task(client, headers, "Failing Task 1")
        t2 = await create_and_start_task(client, headers, "Queued Task 2")

        monkeypatch.setattr("app.worker.research_graph", fail_graph)
        with pytest.raises(RuntimeError, match="Simulated failure"):
            await run_langgraph_workflow(t1)

        # In DB, T1 must be FAILED, and T2 must be dispatched automatically
        async with AsyncSessionLocal() as db:
            t1_db = await db.get(ResearchTask, uuid.UUID(t1))
            assert t1_db.status == "FAILED"
            assert t1_db.worker_lease_until is None

        # T2 was dispatched upon T1's failure
        assert t2 in dispatched_ids

        # T2 now runs successfully
        monkeypatch.setattr("app.worker.research_graph", normal_graph)
        t2_res = await run_langgraph_workflow(t2)
        assert t2_res["status"] == "SUCCESS"

        async with AsyncSessionLocal() as db:
            t2_db = await db.get(ResearchTask, uuid.UUID(t2))
            assert t2_db.status == "COMPLETED"

    await engine.dispose()


@pytest.mark.asyncio
async def test_non_running_states_do_not_consume_running_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched_ids: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: dispatched_ids.append(task_id)),
    )

    pause_gate = asyncio.Event()
    controllable_graph = ControllableGraph(pause_event=pause_gate)
    monkeypatch.setattr("app.worker.research_graph", controllable_graph)

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await register_user(client, f"states_{suffix}")

        # Create tasks in various non-running states: WAITING_APPROVAL, QUEUED
        t_waiting = await create_and_start_task(client, headers, "Waiting task")
        async with AsyncSessionLocal() as db:
            tw = await db.get(ResearchTask, uuid.UUID(t_waiting))
            tw.status = "WAITING_APPROVAL"
            await db.commit()

        # User now starts 2 more tasks: both should be admitted to RUNNING because WAITING_* does not count
        t1 = await create_and_start_task(client, headers, "Active Task 1")
        t2 = await create_and_start_task(client, headers, "Active Task 2")

        run_t1 = asyncio.create_task(run_langgraph_workflow(t1))
        run_t2 = asyncio.create_task(run_langgraph_workflow(t2))
        await asyncio.sleep(0.05)

        async with AsyncSessionLocal() as db:
            t1_db = await db.get(ResearchTask, uuid.UUID(t1))
            t2_db = await db.get(ResearchTask, uuid.UUID(t2))
            assert t1_db.status == "RUNNING"
            assert t2_db.status == "RUNNING"

        pause_gate.set()
        assert (await run_t1)["status"] == "SUCCESS"
        assert (await run_t2)["status"] == "SUCCESS"

    await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_consume_extra_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    pause_gate = asyncio.Event()
    controllable_graph = ControllableGraph(pause_event=pause_gate)
    monkeypatch.setattr("app.worker.research_graph", controllable_graph)

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await register_user(client, f"dup_{suffix}")
        t1 = await create_and_start_task(client, headers, "Task 1")

        run_task = asyncio.create_task(run_langgraph_workflow(t1))
        await asyncio.sleep(0.05)

        # Duplicate delivery while already RUNNING
        dup_result = await run_langgraph_workflow(t1)
        assert dup_result["status"] == "IGNORED"

        # Complete the task
        pause_gate.set()
        assert (await run_task)["status"] == "SUCCESS"

        # Duplicate delivery after COMPLETED
        dup_completed = await run_langgraph_workflow(t1)
        assert dup_completed["status"] == "IGNORED"

    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_dispatcher_finalizer_does_not_overwrite_worker_requeue(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a worker receives a dispatched task and requeues it because capacity is full,

    the originating dispatcher's finalizer must not overwrite the requeue as dispatched.
    """
    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await register_user(client, f"stalefin_{suffix}")
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        target_uid = uuid.UUID(me_res.json()["id"])
        task_id = await create_and_start_task(client, headers, "Stale Finalizer Task")

        worker_ran = False

        def publish_interleaved(tid: str) -> None:
            nonlocal worker_ran
            import psycopg2
            conn = psycopg2.connect(settings.POSTGRES_SYNC_URL)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE task_dispatch_outbox SET dispatched_at = NULL, locked_until = NULL, "
                    "last_error = 'User at concurrent running job limit; waiting for capacity' "
                    "WHERE research_task_id = %s",
                    (tid,),
                )
            conn.commit()
            conn.close()
            worker_ran = True

        monkeypatch.setattr(
            task_dispatcher,
            "execute_research_workflow",
            SimpleNamespace(delay=publish_interleaved),
        )

        assert await task_dispatcher.dispatch_one_outbox_event(user_id=target_uid)
        assert worker_ran

        async with AsyncSessionLocal() as db:
            event = (await db.execute(
                select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id == uuid.UUID(task_id))
            )).scalar_one()
            assert event.dispatched_at is None
            assert event.locked_until is None
            assert "waiting for capacity" in (event.last_error or "")

    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_dispatcher_finalizer_does_not_overwrite_newer_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """If another dispatcher reclaims an event after lease expiry,

    the original dispatcher's success or error finalization must not overwrite the newer lease.
    """
    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await register_user(client, f"newerclaim_{suffix}")
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        target_uid = uuid.UUID(me_res.json()["id"])
        task_id = await create_and_start_task(client, headers, "Newer Claim Task")

        new_lease = datetime.now(timezone.utc) + timedelta(seconds=999)

        def publish_reclaimed(tid: str) -> None:
            import psycopg2
            conn = psycopg2.connect(settings.POSTGRES_SYNC_URL)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE task_dispatch_outbox SET locked_until = %s WHERE research_task_id = %s",
                    (new_lease, tid),
                )
            conn.commit()
            conn.close()

        monkeypatch.setattr(
            task_dispatcher,
            "execute_research_workflow",
            SimpleNamespace(delay=publish_reclaimed),
        )

        assert await task_dispatcher.dispatch_one_outbox_event(user_id=target_uid)

        async with AsyncSessionLocal() as db:
            event = (await db.execute(
                select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id == uuid.UUID(task_id))
            )).scalar_one()
            assert event.dispatched_at is None
            assert event.locked_until == new_lease

    await engine.dispose()
