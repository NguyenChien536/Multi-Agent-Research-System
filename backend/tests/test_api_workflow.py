"""API integration checks against an isolated PostgreSQL database.

CI migrates a fresh database before running this module. No Celery worker or
external AI provider is contacted.
"""

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import research as research_endpoint
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.report import ResearchReport


@pytest.mark.asyncio
async def test_auth_and_research_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched: list[str] = []
    monkeypatch.setattr(
        research_endpoint,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: dispatched.append(task_id)),
    )

    suffix = uuid.uuid4().hex[:12]
    users = [
        {"username": f"author_{suffix}", "email": f"author_{suffix}@example.com", "password": "SecurePass123!"},
        {"username": f"reader_{suffix}", "email": f"reader_{suffix}@example.com", "password": "SecurePass123!"},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/research")).status_code == 401

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
        assert (await client.post(f"/api/v1/research/{author_id}/start", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{author_id}/report", headers=reader_headers)).status_code == 404

        started = await client.post(f"/api/v1/research/{author_id}/start", headers=author_headers)
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "PLANNING"
        assert (await client.post(f"/api/v1/research/{author_id}/start", headers=author_headers)).status_code == 409
        assert dispatched == [author_id]

        async with AsyncSessionLocal() as db:
            db.add(ResearchReport(
                research_task_id=uuid.UUID(author_id),
                title="Evidence report",
                content_markdown="# Evidence report",
                word_count=2,
            ))
            await db.commit()

        report = await client.get(f"/api/v1/research/{author_id}/report", headers=author_headers)
        assert report.status_code == 200, report.text
        assert report.json()["research_task_id"] == author_id
        assert (await client.get(f"/api/v1/research/{author_id}/report", headers=reader_headers)).status_code == 404
