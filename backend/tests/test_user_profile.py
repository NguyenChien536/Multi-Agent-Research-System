import asyncio
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.models.task import ResearchTask, TaskDeletionOutbox, WorkflowRun


PASSWORD = "ProfileTestPassword123!"


async def account(client):
    suffix = uuid.uuid4().hex
    value = {"username": "profile_" + suffix, "email": suffix + "@example.com", "password": PASSWORD}
    response = await client.post('/api/v1/auth/register', json=value)
    assert response.status_code == 201
    user = response.json()
    login = await client.post('/api/v1/auth/login', json={"email": value['email'], "password": PASSWORD})
    assert login.status_code == 200
    return user, {"Authorization": "Bearer " + login.json()['access_token']}


@pytest_asyncio.fixture
async def profiles():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        first, headers = await account(client)
        second, other_headers = await account(client)
        try:
            yield client, first, headers, second, other_headers
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(User).where(User.id.in_([uuid.UUID(first['id']), uuid.UUID(second['id'])])))
                await db.commit()


@pytest.mark.asyncio
async def test_profile_patch_is_authenticated_persistent_and_owner_scoped(profiles):
    client, first, headers, second, other = profiles
    assert (await client.patch('/api/v1/auth/me', json={'full_name': 'Not authorized'})).status_code == 401
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(first['id']))
        password_hash = user.password_hash
        user.model_connection = {'private': 'unchanged-encrypted-profile'}
        await db.commit()
    updated = await client.patch('/api/v1/auth/me', headers=headers, json={
        'username': '  changed_' + uuid.uuid4().hex + '  ', 'full_name': '  Nguyễn Đình Chiến  ',
    })
    assert updated.status_code == 200
    assert updated.json()['full_name'] == 'Nguyễn Đình Chiến'
    assert updated.json()['username'].startswith('changed_')
    assert updated.json()['id'] == first['id'] and updated.json()['email'] == first['email']
    assert (await client.get('/api/v1/auth/me', headers=headers)).json() == updated.json()
    assert (await client.get('/api/v1/auth/me', headers=other)).json() == second
    assert 'password_hash' not in updated.text and 'model_connection' not in updated.text
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(first['id']))
        assert user.password_hash == password_hash
        assert user.model_connection == {'private': 'unchanged-encrypted-profile'}
    cleared = await client.patch('/api/v1/auth/me', headers=headers, json={'full_name': '   '})
    assert cleared.status_code == 200 and cleared.json()['full_name'] is None


@pytest.mark.asyncio
async def test_email_change_requires_password_and_new_email_works_for_login(profiles):
    client, first, headers, _, _ = profiles
    new_email = uuid.uuid4().hex + '@example.com'
    for password in (None, 'wrong-password'):
        payload = {'email': new_email, 'full_name': 'Must not be partially saved'}
        if password is not None:
            payload['current_password'] = password
        rejected = await client.patch('/api/v1/auth/me', headers=headers, json=payload)
        assert rejected.status_code == 403
        current = (await client.get('/api/v1/auth/me', headers=headers)).json()
        assert current['email'] == first['email'] and current['full_name'] is None
    response = await client.patch('/api/v1/auth/me', headers=headers, json={
        'email': new_email, 'current_password': PASSWORD,
    })
    assert response.status_code == 200 and response.json()['email'] == new_email
    assert PASSWORD not in response.text
    assert (await client.get('/api/v1/auth/me', headers=headers)).json()['id'] == first['id']
    assert (await client.post('/api/v1/auth/login', json={'email': new_email, 'password': PASSWORD})).status_code == 200
    assert (await client.post('/api/v1/auth/login', json={'email': first['email'], 'password': PASSWORD})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['username', 'email'])
async def test_duplicate_identity_returns_conflict_without_partial_changes(profiles, field):
    client, first, headers, second, _ = profiles
    result = await client.patch('/api/v1/auth/me', headers=headers, json={
        field: second[field], 'full_name': 'Not saved', 'current_password': PASSWORD,
    })
    assert result.status_code == 409
    assert (await client.get('/api/v1/auth/me', headers=headers)).json() == first


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    {}, {'username': None}, {'email': None}, {'username': '  '}, {'email': 'invalid'},
    {'username': 'x' * 51}, {'full_name': 'x' * 101}, {'full_name': False},
    {'id': str(uuid.uuid4()), 'full_name': 'Injected'},
    {'user_id': str(uuid.uuid4()), 'full_name': 'Injected'},
    {'password_hash': 'injected', 'full_name': 'Injected'},
    {'model_connection': {}, 'full_name': 'Injected'},
    {'password': 'replacement-secret', 'full_name': 'Injected'},
])
async def test_invalid_or_privileged_fields_are_rejected(profiles, payload):
    client, first, headers, _, _ = profiles
    result = await client.patch('/api/v1/auth/me', headers=headers, json=payload)
    assert result.status_code == 422
    assert 'replacement-secret' not in result.text
    assert (await client.get('/api/v1/auth/me', headers=headers)).json() == first


@pytest.mark.asyncio
async def test_validation_never_echoes_current_password(profiles):
    client, _, headers, _, _ = profiles
    secret = 'private-password-never-echo'
    for payload in ({'full_name': 'x' * 101, 'current_password': secret},
                    {'email': 'invalid', 'current_password': secret},
                    {'email': 'valid@example.com', 'current_password': '密' * 25}):
        response = await client.patch('/api/v1/auth/me', headers=headers, json=payload)
        assert response.status_code == 422
        assert secret not in response.text and '密' not in response.text


@pytest.mark.asyncio
async def test_concurrent_duplicate_username_has_one_winner(profiles):
    client, _, headers, _, other = profiles
    username = 'race_' + uuid.uuid4().hex
    results = await asyncio.gather(*[
        client.patch('/api/v1/auth/me', headers=owner, json={'username': username})
        for owner in (headers, other)
    ])
    assert sorted(response.status_code for response in results) == [200, 409]


@pytest.mark.asyncio
async def test_account_deletion_requires_authentication_password_and_explicit_confirmation(profiles):
    client, first, headers, _, _ = profiles
    body = {'current_password': PASSWORD, 'confirmation': 'DELETE'}
    assert (await client.request('DELETE', '/api/v1/auth/me', json=body)).status_code == 401
    for changes, expected in [({'confirmation': 'cancel'}, 422), ({'current_password': 'wrong-secret'}, 403),
                              ({'id': str(uuid.uuid4())}, 422), ({'current_password': '密' * 25}, 422)]:
        result = await client.request('DELETE', '/api/v1/auth/me', headers=headers, json={**body, **changes})
        assert result.status_code == expected
        assert PASSWORD not in result.text and 'wrong-secret' not in result.text and '密' not in result.text
    assert (await client.get('/api/v1/auth/me', headers=headers)).json() == first


@pytest.mark.asyncio
async def test_empty_account_deletion_revokes_tokens_then_removes_account(profiles):
    from app.services.account_deletion import progress_account_deletion
    client, first, headers, second, other = profiles
    response = await client.request('DELETE', '/api/v1/auth/me', headers=headers,
                                   json={'current_password': PASSWORD, 'confirmation': 'DELETE'})
    assert response.status_code == 202 and response.json()['status'] == 'DELETING'
    assert (await client.get('/api/v1/auth/me', headers=headers)).status_code == 401
    assert (await client.patch('/api/v1/auth/me', headers=headers, json={'full_name': 'Resurrect'})).status_code == 401
    assert (await client.post('/api/v1/auth/login', json={'email': first['email'], 'password': PASSWORD})).status_code == 401
    assert (await client.get('/api/v1/auth/me', headers=other)).json() == second
    assert await progress_account_deletion()
    async with AsyncSessionLocal() as db:
        assert await db.get(User, uuid.UUID(first['id'])) is None
    assert (await client.get('/api/v1/auth/me', headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_account_cleanup_retries_and_preserves_other_users_files(profiles, monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from app import worker
    from app.services.account_deletion import progress_account_deletion
    from app.services.artifact_store import ArtifactStore
    from app.services.provider_budget import assert_task_active, reserve_provider_call, ResearchTaskStopped

    client, first, headers, _, other = profiles
    payload = {'title': 'Account deletion study', 'research_question': 'How is private research safely deleted?'}
    own = (await client.post('/api/v1/research', json=payload, headers=headers)).json()
    kept = (await client.post('/api/v1/research', json=payload, headers=other)).json()
    own_id, kept_id = uuid.UUID(own['id']), uuid.UUID(kept['id'])
    store = ArtifactStore(str(tmp_path))
    monkeypatch.setattr(worker, 'artifact_store', store)
    own_file = store.save_artifact(own_id, 'private.txt', b'private result')
    kept_file = store.save_artifact(kept_id, 'kept.txt', b'other user result')
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(first['id']))
        user.model_connection = {'private': 'encrypted-user-key'}
        task = await db.get(ResearchTask, own_id)
        task.status = 'RUNNING'
        task.attempt_number = 1
        task.worker_lease_until = datetime.now(timezone.utc) + timedelta(minutes=2)
        task.budget_config = {'_llm_connection': {'secret': 'encrypted-task-key'}}
        await db.commit()
    assert (await client.request('DELETE', '/api/v1/auth/me', headers=headers,
                                json={'current_password': PASSWORD, 'confirmation': 'DELETE'})).status_code == 202
    # Even before the cleanup poll tombstones the task, no new provider call is authorized.
    with pytest.raises(ResearchTaskStopped):
        await assert_task_active(own_id, 1)
    with pytest.raises(ResearchTaskStopped):
        await reserve_provider_call(task_id=own_id, attempt_number=1, kind='search')
    assert await progress_account_deletion()
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, own_id)
        assert task.status == 'DELETING' and '_llm_connection' not in task.budget_config
        assert (await db.get(User, uuid.UUID(first['id']))).model_connection is None
        assert await db.scalar(select(TaskDeletionOutbox.id).where(TaskDeletionOutbox.research_task_id == own_id))
    assert (await worker.run_task_deletion(str(own_id)))['status'] == 'DEFERRED'
    async with AsyncSessionLocal() as db:
        (await db.get(ResearchTask, own_id)).worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    original_delete = store.delete_task_artifacts
    def fail_once(task_id):
        raise OSError('temporary disk problem')
    monkeypatch.setattr(store, 'delete_task_artifacts', fail_once)
    assert (await worker.run_task_deletion(str(own_id)))['status'] == 'RETRY'
    assert not await progress_account_deletion()  # Do not cascade away the durable cleanup intent.
    monkeypatch.setattr(store, 'delete_task_artifacts', original_delete)
    assert (await worker.run_task_deletion(str(own_id)))['status'] == 'DELETED'
    assert await progress_account_deletion()
    assert store.get_artifact_path(own_id, own_file['file_path']) is None
    assert store.get_artifact_path(kept_id, kept_file['file_path']).read_bytes() == b'other user result'
    assert (await client.get('/api/v1/research/' + kept['id'], headers=other)).status_code == 200
    async with AsyncSessionLocal() as db:
        assert await db.get(User, uuid.UUID(first['id'])) is None


@pytest.mark.asyncio
async def test_inflight_task_creation_cannot_escape_account_deletion(profiles):
    from app.services.account_deletion import progress_account_deletion
    from app.worker import run_task_deletion
    client, first, headers, _, _ = profiles
    create, removed = await asyncio.gather(
        client.post('/api/v1/research', headers=headers, json={
            'title': 'Concurrent creation', 'research_question': 'Can a task escape account deletion?'}),
        client.request('DELETE', '/api/v1/auth/me', headers=headers,
                       json={'current_password': PASSWORD, 'confirmation': 'DELETE'}),
    )
    assert removed.status_code == 202 and create.status_code in (201, 401)
    if create.status_code == 201:
        assert await progress_account_deletion()
        assert (await run_task_deletion(create.json()['id']))['status'] == 'DELETED'
    assert await progress_account_deletion()
    async with AsyncSessionLocal() as db:
        assert await db.get(User, uuid.UUID(first['id'])) is None


@pytest.mark.asyncio
async def test_account_cleanup_erases_real_checkpoint_threads(profiles, monkeypatch, tmp_path):
    from app import worker
    from app.core.config import settings
    from app.services.account_deletion import progress_account_deletion
    from app.services.artifact_store import ArtifactStore
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    client, _, headers, _, _ = profiles
    task = (await client.post('/api/v1/research', headers=headers, json={
        'title': 'Checkpoint erasure', 'research_question': 'Is saved graph state erased with the account?'})).json()
    thread_id = str(uuid.uuid4())
    other_thread = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(WorkflowRun(research_task_id=uuid.UUID(task['id']), run_number=1, status='WAITING_USER_DATA',
                           checkpoint_thread_id=thread_id))
        await db.commit()
    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as saver:
        await saver.setup()
        for thread in (thread_id, other_thread):
            checkpoint = empty_checkpoint()
            checkpoint['channel_values'] = {'private': 'private graph content'}
            checkpoint['channel_versions'] = {'private': '1'}
            await saver.aput({'configurable': {'thread_id': thread, 'checkpoint_ns': ''}}, checkpoint,
                             {'source': 'input', 'step': 0, 'parents': {}}, {'private': '1'})
    monkeypatch.setattr(worker, 'artifact_store', ArtifactStore(str(tmp_path)))
    assert (await client.request('DELETE', '/api/v1/auth/me', headers=headers,
                                json={'current_password': PASSWORD, 'confirmation': 'DELETE'})).status_code == 202
    assert await progress_account_deletion()
    assert (await worker.run_task_deletion(task['id']))['status'] == 'DELETED'
    assert await progress_account_deletion()
    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as saver:
        assert await saver.aget_tuple({'configurable': {'thread_id': thread_id}}) is None
        assert await saver.aget_tuple({'configurable': {'thread_id': other_thread}}) is not None
        await saver.adelete_thread(other_thread)
