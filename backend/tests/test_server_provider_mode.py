import uuid

import httpx
import pytest

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.services.model_connection import ModelConnectionInput, open_connection, seal_connection
from app.services.user_model_settings import decode_input, settings_id
from tests.test_provider_budget import create_running_task, delete_test_user


def test_server_mode_bypasses_stored_connections_without_destroying_them(monkeypatch):
    owner, task = uuid.uuid4(), uuid.uuid4()
    value = ModelConnectionInput(api_key='fake-private-user-key', base_url='https://api.groq.com/openai/v1',
                                 model='test-model', input_price_per_million=0, output_price_per_million=0)
    stored = seal_connection(value, task, owner)
    monkeypatch.setattr(settings, 'USE_SERVER_PROVIDERS', True)
    assert open_connection({'_llm_connection': stored}, task, owner) is None
    assert open_connection({'_llm_connection': {'secret': 'broken-old-key'}}, task, owner) is None
    assert decode_input(stored, owner, task).api_key.get_secret_value() == 'fake-private-user-key'


@pytest.mark.asyncio
async def test_server_mode_task_creation_ignores_web_keys_and_never_exposes_server_secret(monkeypatch):
    _, uid = await create_running_task()
    value = ModelConnectionInput(api_key='fake-saved-key', base_url='https://api.groq.com/openai/v1',
                                 model='old-user-model', input_price_per_million=0, output_price_per_million=0)
    stored = seal_connection(value, settings_id(uid), uid)
    monkeypatch.setattr(settings, 'USE_SERVER_PROVIDERS', True)
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'fake-server-secret')
    monkeypatch.setattr(settings, 'LLM_PROVIDER_PRIORITY', 'gemini')
    try:
        async with AsyncSessionLocal() as db:
            (await db.get(User, uid)).model_connection = stored
            await db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            options = await client.get('/api/v1/research/model-connections/options')
            assert options.json()['use_server_providers'] and options.json()['server_provider_ready']
            assert options.json()['server_provider'] == 'gemini'
            assert 'fake-server-secret' not in options.text
            result = await client.post('/api/v1/research', headers={'Authorization': 'Bearer ' + create_access_token(uid)},
                                       json={'title': 'Server provider demo', 'research_question': 'Can this run use the server without web API setup?'})
            assert result.status_code == 201 and result.json()['model_connection'] is None
        async with AsyncSessionLocal() as db:
            assert (await db.get(User, uid)).model_connection == stored
    finally:
        await delete_test_user(uid)
