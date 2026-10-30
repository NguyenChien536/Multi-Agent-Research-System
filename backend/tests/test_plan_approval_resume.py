from tests.manuscript_helpers import supported_critic_response
"""Integration tests for Human-in-the-Loop (HITL) Plan Approval and Workflow Pause/Resume (P4 / Gate G4)."""

import re
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents import nodes as nodes_module
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.report import ResearchReport, ReportVersion
from app.models.source import DocumentChunk
from app.tools.search import SearchResult
from app.worker import run_langgraph_workflow
from tests.manuscript_helpers import complete_manuscript


async def _register_and_login(client: AsyncClient, suffix: str):
    reg = await client.post("/api/v1/auth/register", json={
        "username": f"hitl_{suffix}",
        "email": f"hitl_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    assert reg.status_code == 201
    login = await client.post("/api/v1/auth/login", json={
        "email": f"hitl_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_hitl_plan_approval_pause_and_resume(monkeypatch):
    """Kiểm tra quy trình HITL: Dừng tại WAITING_APPROVAL, phê duyệt kế hoạch, và tiếp tục chạy hoàn tất."""
    suffix = uuid.uuid4().hex[:8]

    # Mock LLM & Leaf tools
    plan_mock = nodes_module.SupervisorPlan(
        research_angle="comparative multi-agent analysis",
        search_queries=["ai healthcare 1", "ai healthcare 2"],
        required_sections=["Overview", "Methodology", "Results"],
    )
    supervisor_plan_calls = 0

    class FakeStructuredLLM:
        def __init__(self, schema=None):
            self.schema = schema

        def with_structured_output(self, schema):
            return FakeStructuredLLM(schema=schema)

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, _messages):
            nonlocal supervisor_plan_calls
            if self.schema is nodes_module.SupervisorPlan:
                supervisor_plan_calls += 1
                return plan_mock
            if self.schema is nodes_module.AnalystExtraction:
                return nodes_module.AnalystExtraction(claims=[
                    nodes_module.ExtractedClaim(
                        claim="Clinical multi-agent systems improve diagnostic accuracy.",
                        evidence_quote="The source provides supporting evidence.",
                    )
                ])
            if self.schema is nodes_module.CriticVerdict:
                return supported_critic_response(_messages)
            raise AssertionError(f"Unexpected schema: {self.schema}")

    class FakeWriterLLM:
        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, messages):
            prompt = str(messages)
            claim_id_match = re.search(r"\[\[@claim:([0-9a-f-]{36})\]\]", prompt)
            claim_ref = f" [[@claim:{claim_id_match.group(1)}]]" if claim_id_match else ""
            return SimpleNamespace(content=complete_manuscript(f"Clinical Multi-Agent Systems\nEvidence found.{claim_ref}", prompt=prompt))

    monkeypatch.setattr(nodes_module, "get_fast_llm", FakeStructuredLLM)
    monkeypatch.setattr(nodes_module, "get_smart_llm", FakeWriterLLM)

    async def fake_search(_queries, max_results_per_query=3, budget_context=None, **kwargs):
        return [SearchResult(
            title="Clinical Multi-Agent Systems",
            url="https://health-ai.org/paper1",
            content="The source provides supporting evidence.",
        )]

    async def fake_fetch(urls, max_concurrent=5):
        return {url: "The source provides supporting evidence." for url in urls}

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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_owner = await _register_and_login(client, f"owner_{suffix}")
        headers_other = await _register_and_login(client, f"other_{suffix}")

        # 1. Tạo task với require_plan_approval = True
        create_res = await client.post(
            "/api/v1/research",
            json={
                "title": "HITL Research Task",
                "research_question": "Ứng dụng Multi-Agent trong Y tế lâm sàng",
                "require_plan_approval": True,
            },
            headers=headers_owner,
        )
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

        # Bắt đầu task -> QUEUED
        start_res = await client.post(f"/api/v1/research/{task_id}/start", headers=headers_owner)
        assert start_res.status_code == 202

        # 2. Chạy worker lần 1 -> Phải dừng tại WAITING_APPROVAL
        worker_result = await run_langgraph_workflow(task_id)
        assert worker_result["status"] == "WAITING_APPROVAL"
        assert supervisor_plan_calls == 1

        # Kiểm tra database: task ở trạng thái WAITING_APPROVAL, current_step là Supervisor, worker lease đã giải phóng
        async with AsyncSessionLocal() as session:
            task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            assert task is not None
            assert task.status == "WAITING_APPROVAL"
            assert task.current_step == "Supervisor"
            assert task.plan is not None
            assert task.plan["research_angle"] == "comparative multi-agent analysis"
            assert task.plan_approved is False
            assert task.worker_lease_until is None

        # 3. Phân quyền: Người dùng khác không được xem hoặc duyệt kế hoạch -> 404
        cross_get = await client.get(f"/api/v1/research/{task_id}/plan", headers=headers_other)
        assert cross_get.status_code == 404

        cross_approve = await client.post(f"/api/v1/research/{task_id}/plan/approve", json={"plan_version": 1}, headers=headers_other)
        assert cross_approve.status_code == 404

        # 4. Chủ sở hữu xem kế hoạch (GET /plan)
        get_plan_res = await client.get(f"/api/v1/research/{task_id}/plan", headers=headers_owner)
        assert get_plan_res.status_code == 200
        plan_data = get_plan_res.json()
        assert plan_data["status"] == "WAITING_APPROVAL"
        assert plan_data["plan_approved"] is False
        assert len(plan_data["plan"]["search_queries"]) == 2

        stale_approval = await client.post(
            f"/api/v1/research/{task_id}/plan/approve",
            json={"plan_version": plan_data["plan_version"] + 1},
            headers=headers_owner,
        )
        assert stale_approval.status_code == 409

        # 5. Chủ sở hữu duyệt kế hoạch kèm chỉnh sửa truy vấn (POST /plan/approve)
        approved_queries = ["ai multi-agent clinical diagnostic 2026", "healthcare agents safety"]
        approve_res = await client.post(
            f"/api/v1/research/{task_id}/plan/approve",
            json={
                "plan_version": plan_data["plan_version"],
                "approved_queries": approved_queries,
                "feedback": "Tập trung vào độ an toàn và chẩn đoán lâm sàng",
            },
            headers=headers_owner,
        )
        assert approve_res.status_code == 200
        approved_task = approve_res.json()
        assert approved_task["status"] == "QUEUED"
        assert approved_task["plan_approved"] is True
        assert approved_task["plan"]["search_queries"] == approved_queries

        # 6. Chạy worker lần 2 -> Tiếp tục từ Researcher và hoàn tất báo cáo
        resumed_result = await run_langgraph_workflow(task_id)
        assert resumed_result["status"] == "SUCCESS"
        assert supervisor_plan_calls == 1, "The resumed workflow must continue from its checkpoint, not re-plan."

        # 7. Kiểm tra kết quả trong DB: Task COMPLETED, có ResearchReport
        async with AsyncSessionLocal() as session:
            final_task = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            assert final_task.status == "COMPLETED"
            assert final_task.plan_approved is True
            assert final_task.plan["search_queries"] == approved_queries

            report = await session.scalar(select(ResearchReport).where(ResearchReport.research_task_id == final_task.id))
            assert report is not None
            version = await session.scalar(select(ReportVersion).where(ReportVersion.report_id == report.id))
            assert version is not None
            assert version.version_number == 1
            assert "Clinical Multi-Agent Systems" in version.content_markdown


@pytest.mark.asyncio
async def test_hitl_plan_rejection_flow(monkeypatch):
    """Kiểm tra từ chối kế hoạch: Reset plan_approved và lưu ý kiến góp ý."""
    suffix = uuid.uuid4().hex[:8]

    plan_mock = nodes_module.SupervisorPlan(
        research_angle="initial angle",
        search_queries=["finance ai 1"],
        required_sections=["Intro", "Details"],
    )

    class FakeSupervisorLLM:
        def with_structured_output(self, _schema):
            return self
        def with_fallbacks(self, _fallbacks):
            return self
        async def ainvoke(self, _messages):
            return plan_mock

    monkeypatch.setattr(nodes_module, "get_fast_llm", FakeSupervisorLLM)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"rej_{suffix}")

        create_res = await client.post(
            "/api/v1/research",
            json={
                "title": "Reject Plan Task",
                "research_question": "Phân tích tài chính AI ngân hàng",
                "require_plan_approval": True,
            },
            headers=headers,
        )
        task_id = create_res.json()["id"]
        await client.post(f"/api/v1/research/{task_id}/start", headers=headers)

        await run_langgraph_workflow(task_id)

        # Từ chối kế hoạch
        reject_res = await client.post(
            f"/api/v1/research/{task_id}/plan/reject",
            json={"plan_version": 1, "reason": "Kế hoạch chưa bao quát rủi ro thanh khoản"},
            headers=headers,
        )
        assert reject_res.status_code == 200
        rejected_task = reject_res.json()
        assert rejected_task["status"] == "QUEUED"
        assert rejected_task["plan_approved"] is False
        assert rejected_task["plan"] is None
        assert rejected_task["plan_feedback"] == "Kế hoạch chưa bao quát rủi ro thanh khoản"


@pytest.mark.asyncio
async def test_waiting_approval_does_not_block_concurrent_tasks(monkeypatch):
    """Kiểm tra tính độc lập: Task A ở WAITING_APPROVAL không chiếm hạn ngạch RUNNING của Task B."""
    suffix = uuid.uuid4().hex[:8]

    plan_mock = nodes_module.SupervisorPlan(
        research_angle="angle a",
        search_queries=["query a"],
        required_sections=["Section A"],
    )

    class FakeSupervisorLLM:
        def with_structured_output(self, _schema):
            return self
        def with_fallbacks(self, _fallbacks):
            return self
        async def ainvoke(self, _messages):
            return plan_mock

    monkeypatch.setattr(nodes_module, "get_fast_llm", FakeSupervisorLLM)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"conc_{suffix}")

        # Task A: require_plan_approval = True -> dừng ở WAITING_APPROVAL
        res_a = await client.post(
            "/api/v1/research",
            json={
                "title": "Task A Waiting Approval",
                "research_question": "Đề tài nghiên cứu ứng dụng thực nghiệm A",
                "require_plan_approval": True,
            },
            headers=headers,
        )
        assert res_a.status_code == 201, res_a.text
        task_a_id = res_a.json()["id"]
        await client.post(f"/api/v1/research/{task_a_id}/start", headers=headers)

        result_a = await run_langgraph_workflow(task_a_id)
        assert result_a["status"] == "WAITING_APPROVAL"

        # Task B: Chạy bình thường mà không bị chặn bởi Task A
        res_b = await client.post(
            "/api/v1/research",
            json={
                "title": "Task B Independent Run",
                "research_question": "Đề tài nghiên cứu ứng dụng thực nghiệm B",
                "require_plan_approval": False,
            },
            headers=headers,
        )
        assert res_b.status_code == 201, res_b.text
        task_b_id = res_b.json()["id"]
        start_b = await client.post(f"/api/v1/research/{task_b_id}/start", headers=headers)
        assert start_b.status_code == 202

        # Task B có thể được claim và chạy ngay mà không bị chặn
        async with AsyncSessionLocal() as session:
            task_b = await session.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_b_id)))
            assert task_b.status == "QUEUED"
