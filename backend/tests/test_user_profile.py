import asyncio
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User


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
