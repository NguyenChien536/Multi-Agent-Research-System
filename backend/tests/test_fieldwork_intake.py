import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func

from app.api.v1.endpoints import research
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.report import ExportArtifact
from app.models.task import ResearchTask, TaskDispatchOutbox, WorkflowRun
from app.services.artifact_store import ArtifactStore
from app.services.fieldwork_intake import validate_fieldwork_result, MAX_RESULT_BYTES


@pytest.fixture(autouse=True)
def isolated_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(research, 'artifact_store', ArtifactStore(str(tmp_path)))


async def login(client):
    suffix = uuid.uuid4().hex[:10]
    data = {'username': 'field_' + suffix, 'email': suffix + '@example.com', 'password': 'SafeTest123!'}
    assert (await client.post('/api/v1/auth/register', json=data)).status_code == 201
    response = await client.post('/api/v1/auth/login', json=data)
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


async def waiting_task(client, headers, research_type='EMPIRICAL_HUMAN', status='WAITING_USER_DATA'):
    response = await client.post('/api/v1/research', headers=headers, json={
        'title': 'Fieldwork test', 'research_question': 'What does the collected dataset show?',
        'research_type': research_type,
    })
    assert response.status_code == 201
    task_id = response.json()['id']
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, uuid.UUID(task_id))
        task.status = status
        task.plan_version = 1
        db.add(WorkflowRun(
            research_task_id=task.id,
            run_number=1,
            plan_version=1,
            status=status,
            checkpoint_thread_id=str(uuid.uuid4()),
        ))
        await db.commit()
    return task_id


async def upload(client, headers, task_id):
    response = await client.post(f'/api/v1/research/{task_id}/data/files', headers=headers,
        files={'file': ('results.csv', b'group,count\nA,12\nB,8\n', 'text/csv')})
    assert response.status_code == 201, response.text
    return response.json()['artifact_id']


def submission(artifact_id):
    return {'plan_version': 1, 'sample_size': 20, 'method_notes': 'Collected with a predefined questionnaire.',
            'results_summary': 'Group A contained 12 responses and group B contained 8.',
            'data_provenance': 'Synthetic test fixture, researcher example, 2026-10-23.',
            'file_artifact_id': artifact_id}


@pytest.mark.asyncio
async def test_valid_file_resume_serializes_uuid_and_duplicate_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        headers = await login(client)
        task_id = await waiting_task(client, headers)
        artifact_id = await upload(client, headers, task_id)
        stale_resume = await client.post(
            f'/api/v1/research/{task_id}/data/resume',
            headers=headers,
            json={**submission(artifact_id), 'plan_version': 2},
        )
        assert stale_resume.status_code == 409
        responses = await asyncio.gather(*[
            client.post(f'/api/v1/research/{task_id}/data/resume', headers=headers, json=submission(artifact_id))
            for _ in range(2)
        ])
        assert sorted(r.status_code for r in responses) == [200, 409]
        result = next(r.json() for r in responses if r.status_code == 200)
        assert result['status'] == 'QUEUED'
        assert result['user_data_submission']['file_artifact_id'] == artifact_id
        evidence = result['user_data_submission']['artifact_evidence']
        assert len(evidence['sha256_hash']) == 64
        assert evidence['verification_status'] == 'USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED'
        assert evidence['rows_count'] == 2
        async with AsyncSessionLocal() as db:
            assert await db.scalar(select(func.count()).select_from(TaskDispatchOutbox).where(
                TaskDispatchOutbox.research_task_id == uuid.UUID(task_id))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['missing_file', 'missing_provenance', 'blank_provenance',
    'foreign_owner', 'other_task', 'unknown_file', 'wrong_artifact_type', 'missing_bytes', 'wrong_size'])
async def test_invalid_intake_leaves_task_waiting_without_outbox(failure):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        headers = await login(client)
        task_id = await waiting_task(client, headers)
        artifact_id = await upload(client, headers, task_id)
        data = submission(artifact_id)
        if failure == 'missing_file':
            del data['file_artifact_id']
        elif failure == 'missing_provenance':
            del data['data_provenance']
        elif failure == 'blank_provenance':
            data['data_provenance'] = ' ' * 20
        elif failure in {'foreign_owner', 'other_task'}:
            other_headers = await login(client) if failure == 'foreign_owner' else headers
            other_id = await waiting_task(client, other_headers)
            data['file_artifact_id'] = await upload(client, other_headers, other_id)
        elif failure == 'unknown_file':
            data['file_artifact_id'] = str(uuid.uuid4())
        else:
            async with AsyncSessionLocal() as db:
                art = await db.get(ExportArtifact, uuid.UUID(artifact_id))
                if failure == 'wrong_artifact_type':
                    art.export_type = 'PROTOCOL'
                elif failure == 'wrong_size':
                    art.file_size_bytes += 1
                else:
                    research.artifact_store.delete_artifact(uuid.UUID(task_id), art.file_path)
                await db.commit()
        response = await client.post(f'/api/v1/research/{task_id}/data/resume', headers=headers, json=data)
        assert response.status_code == 422, response.text
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, uuid.UUID(task_id))
            assert task.status == 'WAITING_USER_DATA'
            assert task.user_data_submission is None
            assert await db.scalar(select(func.count()).select_from(TaskDispatchOutbox).where(
                TaskDispatchOutbox.research_task_id == task.id)) == 0


@pytest.mark.asyncio
async def test_file_upload_and_resume_enforce_auth_and_task_owner():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner, other = await login(client), await login(client)
        task_id = await waiting_task(client, owner)
        artifact_id = await upload(client, owner, task_id)
        for headers, expected in [({}, 401), (other, 404)]:
            upload_response = await client.post(f'/api/v1/research/{task_id}/data/files', headers=headers,
                files={'file': ('result.txt', b'Observed results from the study.', 'text/plain')})
            assert upload_response.status_code == expected
            response = await client.post(f'/api/v1/research/{task_id}/data/resume', headers=headers, json=submission(artifact_id))
            assert response.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('research_type,status', [('REVIEW', 'WAITING_USER_DATA'),
    ('EMPIRICAL_COMPUTATIONAL', 'WAITING_USER_DATA'), ('EMPIRICAL_HUMAN', 'RUNNING'), ('EMPIRICAL_HUMAN', 'CANCELLED')])
async def test_wrong_study_type_or_state_rejects_upload_and_resume(research_type, status):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        headers = await login(client)
        task_id = await waiting_task(client, headers, research_type, status)
        response = await client.post(f'/api/v1/research/{task_id}/data/files', headers=headers,
            files={'file': ('result.txt', b'Observed results from the study.', 'text/plain')})
        assert response.status_code == 409
        response = await client.post(f'/api/v1/research/{task_id}/data/resume', headers=headers,
            json=submission(str(uuid.uuid4())))
        assert response.status_code == 409


@pytest.mark.parametrize('filename,content', [('data.exe', b'data'), ('data.txt', b''),
    ('data.txt', b'\x00data'), ('data.txt', b'\xff\xfe'), ('data.csv', b'a,b\n1\n'),
    ('data.csv', b'a,a\n1,2\n'), ('data.csv', b'a,b\n'), ('data.csv', b'a,b\n"unterminated,1\n')])
def test_invalid_file_content_is_rejected(filename, content):
    with pytest.raises(ValueError):
        validate_fieldwork_result(filename, content)


@pytest.mark.asyncio
async def test_upload_limits_and_invalid_content_leave_no_artifacts(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        headers = await login(client)
        task_id = await waiting_task(client, headers)
        for filename, content, expected in [('data.txt', b'x' * (MAX_RESULT_BYTES + 1), 413),
                ('data.csv', b'a,b\n1\n', 422), ('data.pdf', b'%PDF-data', 422)]:
            response = await client.post(f'/api/v1/research/{task_id}/data/files', headers=headers,
                files={'file': (filename, content, 'application/octet-stream')})
            assert response.status_code == expected
        async with AsyncSessionLocal() as db:
            assert await db.scalar(select(func.count()).select_from(ExportArtifact).where(
                ExportArtifact.research_task_id == uuid.UUID(task_id))) == 0
        monkeypatch.setattr(research.settings, 'MAX_UPLOAD_FILES_PER_TASK', 1)
        await upload(client, headers, task_id)
        response = await client.post(f'/api/v1/research/{task_id}/data/files', headers=headers,
            files={'file': ('second.txt', b'Some more user-provided observations.', 'text/plain')})
        assert response.status_code == 409
