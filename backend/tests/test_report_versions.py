"""API and database guarantees for immutable report versions."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.grounding import Citation
from app.models.report import ReportVersion, ResearchReport
from app.models.source import ResearchSource
from app.models.task import ResearchTask


async def _register_and_login(client: AsyncClient, username: str) -> dict[str, str]:
    email = f"{username}@example.com"
    response = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": "SecurePass123!",
    })
    assert response.status_code == 201, response.text
    response = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "SecurePass123!",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_report_versions_are_stable_ordered_and_owner_scoped():
    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers = await _register_and_login(client, f"report_owner_{suffix}")
        reader_headers = await _register_and_login(client, f"report_reader_{suffix}")
        created = await client.post("/api/v1/research", headers=owner_headers, json={
            "title": f"Versioned report {suffix}",
            "research_question": "How do immutable report versions preserve research history?",
        })
        assert created.status_code == 201, created.text
        task_id = uuid.UUID(created.json()["id"])

        async with AsyncSessionLocal() as session:
            task = await session.get(ResearchTask, task_id)
            report = ResearchReport(research_task_id=task_id)
            session.add(report)
            await session.flush()
            primary_report_id = report.id
            source = ResearchSource(
                research_task_id=task_id,
                source_tag="src_01",
                title="Versioning study",
                url="https://example.com/versioning",
            )
            session.add(source)
            await session.flush()
            primary_source_id = source.id
            first = ReportVersion(
                report_id=report.id,
                version_number=1,
                plan_version=task.plan_version,
                title="Initial report",
                content_markdown="# Original report",
                executive_summary="Original summary",
                review_status="NEEDS_REVIEW",
                review_metadata={"findings": ["old citation context"]},
                word_count=3,
            )
            second = ReportVersion(
                report_id=report.id,
                version_number=2,
                plan_version=task.plan_version,
                title="Revised report",
                content_markdown="# Revised report",
                executive_summary="Revised summary",
                review_status="PASSED",
                review_metadata={"findings": []},
                word_count=3,
            )
            session.add_all([first, second])
            await session.flush()
            session.add_all([
                Citation(
                    research_task_id=task_id,
                    report_id=report.id,
                    report_version_id=first.id,
                    source_id=source.id,
                    citation_label="[1]",
                    citation_number=1,
                    claim_text="Claim from original version",
                ),
                Citation(
                    research_task_id=task_id,
                    report_id=report.id,
                    report_version_id=second.id,
                    source_id=source.id,
                    citation_label="[1]",
                    citation_number=1,
                    claim_text="Claim from revised version",
                ),
            ])
            await session.commit()

        latest = await client.get(f"/api/v1/research/{task_id}/report", headers=owner_headers)
        assert latest.status_code == 200, latest.text
        assert latest.json()["version_number"] == 2
        assert latest.json()["content_markdown"] == "# Revised report"
        assert latest.json()["executive_summary"] == "Revised summary"

        versions = await client.get(f"/api/v1/research/{task_id}/report/versions", headers=owner_headers)
        assert versions.status_code == 200, versions.text
        assert [item["version_number"] for item in versions.json()] == [2, 1]

        original = await client.get(
            f"/api/v1/research/{task_id}/report/versions/1",
            headers=owner_headers,
        )
        assert original.status_code == 200, original.text
        assert original.json()["content_markdown"] == "# Original report"
        assert original.json()["review_metadata"] == {"findings": ["old citation context"]}

        current_citations = await client.get(f"/api/v1/research/{task_id}/citations", headers=owner_headers)
        assert current_citations.status_code == 200, current_citations.text
        assert [item["claim_text"] for item in current_citations.json()] == ["Claim from revised version"]
        historical_citations = await client.get(
            f"/api/v1/research/{task_id}/report/versions/1/citations",
            headers=owner_headers,
        )
        assert historical_citations.status_code == 200, historical_citations.text
        assert [item["claim_text"] for item in historical_citations.json()] == ["Claim from original version"]

        assert (await client.get(f"/api/v1/research/{task_id}/report/versions", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{task_id}/report/versions/1/citations", headers=reader_headers)).status_code == 404
        assert (await client.get(f"/api/v1/research/{task_id}/report/versions/99", headers=owner_headers)).status_code == 404

        async with AsyncSessionLocal() as session:
            report = await session.scalar(select(ResearchReport).where(ResearchReport.research_task_id == task_id))
            session.add(ReportVersion(
                report_id=report.id,
                version_number=2,
                title="Duplicate version",
                content_markdown="Must fail",
                review_status="NEEDS_REVIEW",
                review_metadata={},
                word_count=2,
            ))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

        second_task_response = await client.post("/api/v1/research", headers=owner_headers, json={
            "title": f"Other report {suffix}",
            "research_question": "Can a citation reference another report's version?",
        })
        assert second_task_response.status_code == 201, second_task_response.text
        second_task_id = uuid.UUID(second_task_response.json()["id"])
        async with AsyncSessionLocal() as session:
            other_report = ResearchReport(research_task_id=second_task_id)
            session.add(other_report)
            await session.flush()
            other_version = ReportVersion(
                report_id=other_report.id,
                version_number=1,
                title="Other report version",
                content_markdown="# Other report",
                review_status="NEEDS_REVIEW",
                review_metadata={},
                word_count=2,
            )
            session.add(other_version)
            await session.commit()
            session.add(Citation(
                research_task_id=task_id,
                report_id=primary_report_id,
                report_version_id=other_version.id,
                source_id=primary_source_id,
                citation_label="[99]",
                claim_text="Must not be attached to a different report version",
            ))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
