"""Exercise the API -> graph -> worker -> persisted report path on CI's real DB.

Provider boundaries are deterministic here. A live provider demo is a separate
release gate because it needs credentials and network access.
"""

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents import graph as graph_module
from app.api.v1.endpoints import research as research_endpoint
from app.main import app
from app import worker


@pytest.mark.asyncio
async def test_demo_path_persists_report(monkeypatch: pytest.MonkeyPatch) -> None:
    visited: list[str] = []
    queued: list[str] = []

    def node(name: str, output: dict):
        async def run(_state: dict) -> dict:
            visited.append(name)
            return {"current_agent": name, **output}
        return run

    monkeypatch.setattr(graph_module, "supervisor_node", node("supervisor", {
        "plan": {"required_sections": ["Overview", "References"]},
        "delta_queries": ["traceable research"],
        "current_queries": ["traceable research"],
    }))
    monkeypatch.setattr(graph_module, "researcher_node", node("researcher", {
        "collected_sources": [{"source_tag": "src_01", "url": "https://example.com/source"}],
        "current_iteration": 1,
    }))
    monkeypatch.setattr(graph_module, "curator_node", node("curator", {"indexed_chunks_count": 1}))
    monkeypatch.setattr(graph_module, "analyst_node", node("analyst", {
        "claims": [{"claim": "A claim is backed by a source", "source_tag": "src_01"}],
    }))
    monkeypatch.setattr(graph_module, "writer_node", node("writer", {
        "draft_report_markdown": "# Overview\nA sourced finding [1].\n\n# References\n[1] Example source.",
    }))
    monkeypatch.setattr(graph_module, "critic_node", node("critic", {"critic_verdict": "PASS"}))
    monkeypatch.setattr(graph_module, "post_processor_node", node("post_processor", {
        "final_report_markdown": "# Overview\nA sourced finding [1].\n\n# References\n[1] Example source.",
        "status": "COMPLETED",
    }))
    monkeypatch.setattr(worker, "research_graph", graph_module.build_research_graph())
    monkeypatch.setattr(
        research_endpoint,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: queued.append(task_id)),
    )

    suffix = uuid.uuid4().hex[:12]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registered = await client.post("/api/v1/auth/register", json={
            "username": f"demo_{suffix}",
            "email": f"demo_{suffix}@example.com",
            "password": "SecurePass123!",
        })
        assert registered.status_code == 201, registered.text
        login = await client.post("/api/v1/auth/login", json={
            "email": f"demo_{suffix}@example.com",
            "password": "SecurePass123!",
        })
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        created = await client.post("/api/v1/research", headers=headers, json={
            "title": "End-to-end demo",
            "research_question": "How are research claims traced to sources?",
            "research_depth": "STANDARD",
        })
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]
        started = await client.post(f"/api/v1/research/{task_id}/start", headers=headers)
        assert started.status_code == 200, started.text
        assert queued == [task_id]

        completed = await worker.run_langgraph_workflow(task_id)
        assert completed["status"] == "SUCCESS"
        status = await client.get(f"/api/v1/research/{task_id}", headers=headers)
        assert status.status_code == 200, status.text
        assert status.json()["status"] == "COMPLETED"
        report = await client.get(f"/api/v1/research/{task_id}/report", headers=headers)
        assert report.status_code == 200, report.text
        assert report.json()["research_task_id"] == task_id
        assert "# References" in report.json()["content_markdown"]

    assert visited == [
        "supervisor", "researcher", "curator", "analyst", "writer", "critic", "post_processor",
    ]
