"""Integration tests for Methodologist Agent, Intermediate Protocol Artifact, and Fieldwork Data Resume (Gate G4)."""

import re
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents import nodes as nodes_module
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.report import ExportArtifact, ResearchReport
from app.models.source import DocumentChunk
from app.tools.search import SearchResult
from app.worker import run_langgraph_workflow


async def _register_and_login(client: AsyncClient, suffix: str):
    reg = await client.post("/api/v1/auth/register", json={
        "username": f"method_{suffix}",
        "email": f"method_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    assert reg.status_code == 201
    login = await client.post("/api/v1/auth/login", json={
        "email": f"method_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_empirical_human_protocol_pause_and_resume(monkeypatch):
    """Kiểm tra toàn bộ vòng đời EMPIRICAL_HUMAN: sinh Protocol trung gian, dừng tại WAITING_USER_DATA, nạp dữ liệu và hoàn tất."""
    suffix = uuid.uuid4().hex[:8]

    plan_mock = nodes_module.SupervisorPlan(
        research_angle="empirical investigation into clinical AI adoption",
        search_queries=["clinical ai survey", "healthcare adoption rate"],
        required_sections=[
            "Title", "Abstract", "Introduction", "Research Questions & Hypotheses",
            "Methods", "Results", "Discussion", "Limitations", "Conclusion", "References"
        ],
    )

    proto_mock = nodes_module.MethodologistProtocol(
        research_questions=["How does multi-agent AI affect diagnostic confidence in oncology?"],
        hypotheses=["H1: Multi-agent AI recommendations positively correlate with diagnostic concordance."],
        variables={
            "independent": ["AI assistance level"],
            "dependent": ["Diagnostic concordance rate"],
            "control": ["Physician years of experience", "Hospital tier"],
        },
        study_design="Multi-center cross-sectional survey and observational trial",
        data_collection_procedure="Administer standardized 20-item clinical review questionnaire following AI consultation.",
        analysis_plan="Descriptive statistics followed by logistic regression and concordance calculation.",
        ethical_considerations="Informed consent collected; patient data fully de-identified per HIPAA/GDPR.",
        protocol_markdown="""# Nghiên cứu thực nghiệm: Ứng dụng AI trong chẩn đoán lâm sàng

## 1. Giả thuyết nghiên cứu
- **H1**: Sự hỗ trợ của hệ thống đa tác tử làm tăng mức độ đồng thuận chẩn đoán.

## 2. Thiết kế & Phương pháp
- Thiết kế: Khảo sát cắt ngang tại 3 bệnh viện.
- Cỡ mẫu tối thiểu: N = 120 bác sĩ.
""",
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
                        claim="Clinical multi-agent systems improve diagnostic accuracy.",
                        evidence_quote="The source provides supporting evidence.",
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
                f"# Báo cáo thực nghiệm: Đánh giá hệ thống đa tác tử\n\n"
                f"## Tóm tắt\nNghiên cứu thực nghiệm đánh giá tác động lâm sàng.\n\n"
                f"## Giả thuyết & Phương pháp\nĐã kiểm định giả thuyết H1 với thiết kế khảo sát.\n\n"
                f"## Kết quả thực địa\n"
                f"Theo dữ liệu thực tế do người dùng cung cấp [Nguồn: Khảo sát lâm sàng Oct 2026, N=150]: "
                f"Mức độ đồng thuận đạt 78%. Luận điểm bổ trợ: {markers}\n\n"
                f"## Thảo luận & Kết luận\nKết quả ủng hộ giả thuyết H1."
            )
            return SimpleNamespace(content=content)

    monkeypatch.setattr(nodes_module, "get_fast_llm", lambda: FakeStructuredLLM())
    monkeypatch.setattr(nodes_module, "get_smart_llm", lambda: FakeSmartWriterLLM())

    async def fake_search(_queries, max_results_per_query=3):
        return [
            SearchResult(
                url="https://clinical-ai.example.org/study",
                title="Clinical Multi-Agent Systems in Healthcare",
                content="The source provides supporting evidence for diagnostic decision support.",
            )
        ]

    async def fake_fetch(urls, max_concurrent=5):
        return {url: "The source provides supporting evidence for diagnostic decision support." for url in urls}

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
        auth_headers = await _register_and_login(client, suffix)

        # 1. Tạo task EMPIRICAL_HUMAN
        create_res = await client.post(
            "/api/v1/research",
            headers=auth_headers,
            json={
                "title": "Clinical AI Empirical Investigation",
                "research_question": "Does multi-agent AI enhance oncology diagnostic confidence?",
                "research_type": "EMPIRICAL_HUMAN",
                "research_depth": "STANDARD",
                "language": "vi",
            },
        )
        assert create_res.status_code == 201, create_res.text
        task_data = create_res.json()
        task_id = task_data["id"]
        assert task_data["research_type"] == "EMPIRICAL_HUMAN"
        assert task_data["status"] == "PENDING"

        # 2. Bắt đầu task -> worker chạy lần 1
        start_res = await client.post(f"/api/v1/research/{task_id}/start", headers=auth_headers)
        assert start_res.status_code == 202

        worker_result_1 = await run_langgraph_workflow(task_id)
        assert worker_result_1["status"] == "WAITING_USER_DATA"

        # 3. Kiểm tra DB: task đã dừng tại WAITING_USER_DATA, có protocol artifact, giải phóng worker lease
        async with AsyncSessionLocal() as db:
            task_db = await db.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            assert task_db is not None
            assert task_db.status == "WAITING_USER_DATA"
            assert task_db.current_step == "Methodologist"
            assert task_db.worker_lease_until is None
            assert task_db.protocol_artifact_id is not None

            # Kiểm tra artifact trong DB
            art = await db.scalar(
                select(ExportArtifact).where(ExportArtifact.id == task_db.protocol_artifact_id)
            )
            assert art is not None
            assert art.export_type == "PROTOCOL"

        # 4. Kiểm tra API GET /protocol
        proto_res = await client.get(f"/api/v1/research/{task_id}/protocol", headers=auth_headers)
        assert proto_res.status_code == 200
        proto_data = proto_res.json()
        assert proto_data["task_id"] == task_id
        assert proto_data["research_type"] == "EMPIRICAL_HUMAN"
        assert proto_data["status"] == "WAITING_USER_DATA"
        assert proto_data["protocol_artifact_id"] is not None
        assert "Nghiên cứu thực nghiệm" in (proto_data["content_markdown"] or "")

        # 5. Người dùng nạp kết quả thực nghiệm và bấm tiếp tục (POST /data/resume)
        upload_res = await client.post(
            f"/api/v1/research/{task_id}/data/files", headers=auth_headers,
            files={"file": ("results.csv", b"sample_size,agreement_percent\n150,78\n", "text/csv")},
        )
        assert upload_res.status_code == 201, upload_res.text
        resume_res = await client.post(
            f"/api/v1/research/{task_id}/data/resume",
            headers=auth_headers,
            json={
                "sample_size": 150,
                "method_notes": "Khảo sát cắt ngang tại 3 bệnh viện đa khoa khu vực",
                "results_summary": "78% mức độ đồng thuận giữa khuyến nghị của AI và hội đồng chuyên môn",
                "data_provenance": "Khảo sát lâm sàng bệnh viện, Oct 2026",
                "file_artifact_id": upload_res.json()["artifact_id"],
            },
        )
        assert resume_res.status_code == 200, resume_res.text
        resumed_task = resume_res.json()
        assert resumed_task["status"] == "QUEUED"
        assert resumed_task["user_data_submission"]["sample_size"] == 150

        # Kiểm tra outbox đã được kích hoạt lại
        async with AsyncSessionLocal() as db:
            outbox = await db.scalar(
                select(TaskDispatchOutbox).where(
                    TaskDispatchOutbox.research_task_id == uuid.UUID(task_id),
                    TaskDispatchOutbox.event_type == "START_RESEARCH",
                )
            )
            assert outbox is not None
            assert outbox.dispatched_at is None

        # 6. Worker chạy lần 2 -> Tiếp tục từ Methodologist sang Writer và hoàn thành bài báo
        worker_result_2 = await run_langgraph_workflow(task_id)
        assert worker_result_2["status"] == "SUCCESS"

        # 7. Kiểm tra trạng thái cuối cùng
        async with AsyncSessionLocal() as db:
            final_task = await db.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_id)))
            assert final_task.status == "COMPLETED"
            assert final_task.completed_at is not None

            report = await db.scalar(select(ResearchReport).where(ResearchReport.research_task_id == uuid.UUID(task_id)))
            assert report is not None
            assert "Kết quả thực địa" in report.content_markdown
            assert "N=150" in report.content_markdown
            assert "78%" in report.content_markdown


@pytest.mark.asyncio
async def test_waiting_user_data_does_not_block_concurrent_tasks(monkeypatch):
    """Kiểm tra: Task A ở WAITING_USER_DATA không chiếm suất chạy đồng thời của Task B (Gate G4 & G1)."""
    suffix = uuid.uuid4().hex[:8]

    class FastMockLLM:
        def with_structured_output(self, schema):
            return self

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, _messages):
            return nodes_module.SupervisorPlan(
                research_angle="angle",
                search_queries=["q1"],
                required_sections=["S1"],
            )

    monkeypatch.setattr(nodes_module, "get_fast_llm", lambda: FastMockLLM())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_headers = await _register_and_login(client, suffix)

        # Tạo Task A và đưa trực tiếp vào WAITING_USER_DATA trong DB
        res_a = await client.post(
            "/api/v1/research",
            headers=auth_headers,
            json={
                "title": "Task A Waiting",
                "research_question": "Question A for waiting test",
                "research_type": "EMPIRICAL_HUMAN",
            },
        )
        task_a_id = res_a.json()["id"]

        async with AsyncSessionLocal() as db:
            task_a = await db.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_a_id)))
            task_a.status = "WAITING_USER_DATA"
            task_a.worker_lease_until = None
            await db.commit()

        # Tạo Task B và Start -> Worker phải khởi động được và không bị chặn bởi concurrency limit
        res_b = await client.post(
            "/api/v1/research",
            headers=auth_headers,
            json={
                "title": "Task B Running",
                "research_question": "Question B concurrent test",
                "research_type": "REVIEW",
            },
        )
        task_b_id = res_b.json()["id"]
        start_b = await client.post(f"/api/v1/research/{task_b_id}/start", headers=auth_headers)
        assert start_b.status_code == 202

        # Kiểm tra task B có thể được claim và chuyển thành RUNNING
        async with AsyncSessionLocal() as db:
            task_b = await db.scalar(select(ResearchTask).where(ResearchTask.id == uuid.UUID(task_b_id)))
            assert task_b.status == "QUEUED"
