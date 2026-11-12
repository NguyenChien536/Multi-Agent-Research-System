"""Monitoring exposes durable facts with safe summaries and owner isolation."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.agent_run import AgentRun
from app.models.grounding import ResearchClaim
from app.models.report import ResearchReport, ReportVersion
from app.models.source import ResearchSource
from app.models.task import ResearchTask, WorkflowRun
from app.services.monitoring import next_action, safe_output


async def login(client, suffix):
    email = f"monitor_{suffix}@example.com"
    response = await client.post('/api/v1/auth/register', json={
        'username': f'monitor_{suffix}', 'email': email, 'password': 'SecurePass123!',
    })
    assert response.status_code == 201, response.text
    response = await client.post('/api/v1/auth/login', json={'email': email, 'password': 'SecurePass123!'})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_monitor_snapshot_is_safe_owner_scoped_and_paginated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client, uuid.uuid4().hex[:10])
        other = await login(client, uuid.uuid4().hex[:10])
        response = await client.post('/api/v1/research', headers=owner, json={
            'title': 'Monitor real research steps', 'research_question': 'What supports these research claims?',
        })
        assert response.status_code == 201, response.text
        task_id = uuid.UUID(response.json()['id'])
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            task = await session.get(ResearchTask, task_id)
            task.status = 'RUNNING'
            task.current_step = 'CRITIC'
            task.current_iteration = 2
            task.attempt_number = 3
            task.worker_lease_until = now - timedelta(seconds=5)
            task.budget_config = {'_provider_usage': {'cost_usd': 0.12, 'input_tokens': 25,
                'output_tokens': 15, 'reservations': {'private-reservation': {'cost_usd': 0.05,
                'prompt': 'private secret'}}, 'secret': 'private secret'}}
            workflow = WorkflowRun(research_task_id=task_id, run_number=2, status='RUNNING',
                                   checkpoint_thread_id=uuid.uuid4().hex, plan_version=2)
            report = ResearchReport(research_task_id=task_id)
            session.add_all([workflow, report,
                ResearchSource(research_task_id=task_id, source_tag='src_01', url='https://example.com', ingestion_status='READY'),
                ResearchSource(research_task_id=task_id, source_tag='src_02', url='https://example.com/pending', ingestion_status='PROCESSING'),
                ResearchClaim(research_task_id=task_id, claim_text='private secret', is_verified=True),
            ])
            await session.flush()
            session.add(ReportVersion(report_id=report.id, version_number=1, title='Old draft',
                                      content_markdown='private secret', review_status='NEEDS_REVIEW'))
            for index, name in enumerate(['Researcher', 'Writer', 'Critic']):
                session.add(AgentRun(research_task_id=task_id, agent_name=name,
                    status='FAILED' if name == 'Critic' else 'SUCCESS', iteration=2,
                    started_at=now + timedelta(seconds=index), duration_ms=25,
                    input_summary={'prompt': 'private secret'},
                    output_summary={'draft_words': 42, 'verdict': 'REVISE', 'prompt': 'private secret'},
                    error_message='private secret api-key path' if name == 'Critic' else None,
                    tool_calls=[{'query': 'private secret'}]))
            await session.commit()

        url = f'/api/v1/research/{task_id}/monitor'
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=other)).status_code == 404
        response = await client.get(url + '?limit=2', headers=owner)
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'private, no-store'
        body = response.json()
        assert body['status'] == 'RUNNING'
        assert body['current_step'] == 'CRITIC' and body['current_iteration'] == 2
        assert body['worker_lease_expired'] is True
        assert body['workflow']['run_number'] == 2
        assert body['counts']['sources'] == 2 and body['counts']['pending_sources'] == 1
        assert body['counts']['verified_claims'] == 1 and body['counts']['report_versions'] == 1
        assert body['activity_total'] == 3
        assert [a['agent'] for a in body['activities']] == ['Critic', 'Writer']
        assert body['activities'][0]['has_error'] is True
        assert body['activities'][0]['output'] == {'draft_words': 42, 'verdict': 'REVISE'}
        assert body['estimated_cost_usd'] == pytest.approx(0.12)
        assert body['reserved_cost_usd'] == pytest.approx(0.05)
        assert body['recorded_tokens'] == 40
        assert 'private secret' not in response.text and 'private-reservation' not in response.text
        assert 'checkpoint_thread_id' not in response.text and 'error_message' not in response.text
        page = (await client.get(url + '?offset=2&limit=2', headers=owner)).json()
        assert [a['agent'] for a in page['activities']] == ['Researcher']
        assert (await client.get(url + '?limit=101', headers=owner)).status_code == 422
        assert (await client.get(url + '?offset=-1', headers=owner)).status_code == 422

        async with AsyncSessionLocal() as session:
            task = await session.get(ResearchTask, task_id)
            task.status = 'WAITING_USER_DATA'
            await session.commit()
        body = (await client.get(url, headers=owner)).json()
        assert body['next_action'] == 'UPLOAD_DATA' and body['worker_lease_expired'] is None
        async with AsyncSessionLocal() as session:
            task = await session.get(ResearchTask, task_id)
            task.status = 'DELETING'
            await session.commit()
        assert (await client.get(url, headers=owner)).status_code == 404


@pytest.mark.asyncio
async def test_monitor_empty_history_does_not_invent_progress():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client, uuid.uuid4().hex[:10])
        created = await client.post('/api/v1/research', headers=owner, json={
            'title': 'Not started', 'research_question': 'What will the workflow discover?',
        })
        response = await client.get(f"/api/v1/research/{created.json()['id']}/monitor", headers=owner)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['next_action'] == 'START_RESEARCH'
        assert body['activities'] == [] and body['workflow'] is None
        assert body['current_step'] is None and body['accounting_source'] == 'AGENT_HISTORY'
        assert body['estimated_cost_usd'] == 0 and body['recorded_tokens'] == 0
        assert 'progress_percent' not in body


@pytest.mark.parametrize(('status', 'step', 'report', 'action'), [
    ('WAITING_APPROVAL', 'Supervisor', False, 'REVIEW_PLAN'),
    ('COMPLETED', 'POST_PROCESSOR', True, 'READ_REPORT'),
    ('COMPLETED', 'POST_PROCESSOR', False, 'REPORT_UNAVAILABLE'),
    ('FAILED', 'WRITER', False, 'CHECK_FAILURE'),
    ('CANCELLED', 'WRITER', False, 'CANCELLED'),
    ('NEEDS_REVIEW', 'BUDGET_LIMIT', False, 'REVIEW_LIMIT'),
    ('NEEDS_REVIEW', 'CRITIC', True, 'REVIEW_REPORT'),
    ('NEEDS_REVIEW', 'CRITIC', False, 'REVIEW_RUN'),
    ('QUEUED', None, False, 'WAIT'),
])
def test_monitor_next_action(status, step, report, action):
    assert next_action(status, step, report) == action


def test_monitor_drops_untrusted_summary_values():
    assert safe_output({'verdict': ['secret'], 'repeatability': {'secret': True},
                        'draft_words': True, 'sources_scraped': -1, 'arbitrary': 'secret'}) == {}
    assert safe_output(['secret']) == {}
