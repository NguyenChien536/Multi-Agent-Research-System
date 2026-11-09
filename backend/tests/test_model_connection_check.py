import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import model_connection_check as checks
from app.services.model_connection import ModelConnectionInput, current_connection, build_connection_client, ModelConnection
from tests.test_model_catalog import catalog_transport

KEY = 'fake-probe-key-not-real'
GOOGLE = 'https://generativelanguage.googleapis.com/v1beta/openai'


@pytest.mark.asyncio
async def test_exhausted_account_stops_before_catalog_or_generation(monkeypatch):
    requests=[]
    def handler(request):
        requests.append(request)
        assert str(request.url)=='https://openrouter.ai/api/v1/key'
        return httpx.Response(200,json={'data':{'free_model_daily_requests':{'used':51,'limit':50,'remaining':0}}})
    catalog_transport(monkeypatch,handler)
    discover=AsyncMock()
    monkeypatch.setattr(checks,'discover_models',discover)
    value=ModelConnectionInput(api_key=KEY,base_url='https://openrouter.ai/api/v1',model='fixture:free')
    result=await checks.check_connection(value,generate=True)
    assert result['status']=='quota_exhausted' and result['generation_calls']==0
    assert result['quota']['remaining']==0 and len(requests)==1
    discover.assert_not_called()
    assert KEY not in json.dumps(result)


@pytest.mark.asyncio
async def test_catalog_check_does_not_generate_and_probe_needs_free_confirmation(monkeypatch):
    monkeypatch.setattr(checks,'discover_models',AsyncMock(return_value={'models':[{'id':'gemini-fixture-flash'}]}))
    factory=AsyncMock()
    monkeypatch.setattr(checks,'build_connection_client',factory)
    value=ModelConnectionInput(api_key=KEY,base_url=GOOGLE,model='gemini-fixture-flash')
    assert (await checks.check_connection(value))['status']=='catalog_ok'
    assert (await checks.check_connection(value,generate=True))['status']=='free_tier_confirmation_required'
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected',[(401,'auth_failed'),(503,'unavailable'),(429,'rate_limited')])
async def test_key_check_hides_provider_body_and_does_not_follow_redirects(monkeypatch,status,expected):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status,text=KEY,headers={'location':'https://example.com/leak'})
    catalog_transport(monkeypatch,handler)
    value=ModelConnectionInput(api_key=KEY,base_url='https://openrouter.ai/api/v1',model='fixture:free')
    result=await checks.check_connection(value,generate=True)
    assert result['status']==expected and result['generation_calls']==0
    assert KEY not in json.dumps(result) and len(calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('detail,expected',[
    ('PROVIDER_RATE_LIMIT: private body', 'rate_limited'),
    ('PROVIDER_TIMEOUT: private body', 'timeout'),
    ('PROVIDER_AUTH_FAILED: private body', 'auth_failed'),
])
async def test_catalog_failures_keep_the_actual_category_without_exposing_details(monkeypatch,detail,expected):
    from fastapi import HTTPException
    monkeypatch.setattr(checks,'discover_models',AsyncMock(side_effect=HTTPException(503,detail)))
    result=await checks.check_connection(ModelConnectionInput(api_key=KEY,base_url=GOOGLE,model='gemini-fixture-flash'))
    assert result['status']==expected and result['generation_calls']==0
    assert 'private body' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,content,status',[
    ('json_schema','{"ok":true}','ok'),
    ('prompt_json','{"ok":true}','ok'),
    ('prompt_json','{"ok":false}','invalid_output'),
])
async def test_probe_makes_one_bounded_call_validates_output_and_closes_scope(monkeypatch,mode,content,status):
    monkeypatch.setattr(checks,'discover_models',AsyncMock(return_value={'models':[{'id':'gemini-fixture-flash'}]}))
    seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert body['reasoning_effort']=='low'
        assert body.get('max_completion_tokens',body.get('max_tokens'))==2048
        assert ('response_format' in body)==(mode=='json_schema')
        return httpx.Response(200,json={'id':'probe','object':'chat.completion','created':1,'model':'gemini-fixture-flash',
            'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':18,'completion_tokens':5,'total_tokens':23}})
    clients=[]
    async def factory(connection):
        model=build_connection_client(connection)
        await model.http_async_client.aclose()
        transport=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        model.http_async_client=transport;model.root_async_client._client=transport
        clients.append(transport)
        return model
    # Client construction is synchronous; inject its already initialized transport.
    connection=ModelConnection(base_url=GOOGLE,model='gemini-fixture-flash',api_key=KEY,
        input_price_per_million=0,output_price_per_million=0,output_token_limit=2048,reasoning_effort='none',structured_output_mode=mode)
    client=await factory(connection)
    monkeypatch.setattr(checks,'build_connection_client',lambda probe: probe.register_client(client))
    value=ModelConnectionInput(api_key=KEY,base_url=GOOGLE,model=connection.model,
        output_token_limit=65536,structured_output_mode=mode,reasoning_effort='none')
    result=await checks.check_connection(value,generate=True,free_tier_confirmed=True)
    assert result['status']==status and result['generation_calls']==1
    assert len(seen)==1 and current_connection() is None and clients[0].is_closed
    assert KEY not in json.dumps(result)


@pytest.mark.asyncio
async def test_probe_endpoint_enforces_owner_and_does_not_save_draft(monkeypatch):
    from app.main import app
    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token
    from app.models.user import User
    from tests.test_provider_budget import create_running_task,delete_test_user
    _,uid=await create_running_task()
    other_tid,other_uid=await create_running_task()
    probe=AsyncMock(return_value={'status':'catalog_ok','generation_calls':0})
    monkeypatch.setattr(checks,'check_connection',probe)
    body={'base_url':GOOGLE,'model':'gemini-fixture-flash','api_key':KEY}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            path='/api/v1/settings/model-connection/check'
            assert (await client.post(path,json=body)).status_code==401
            headers={'Authorization':'Bearer '+create_access_token(uid)}
            assert (await client.post(path,json={**body,'task_id':str(other_tid)},headers=headers)).status_code==404
            probe.assert_not_called()
            response=await client.post(path,json=body,headers=headers)
            assert response.status_code==200 and KEY not in response.text
            assert probe.call_args.kwargs['generate'] is False
        async with AsyncSessionLocal() as db:
            assert (await db.get(User,uid)).model_connection is None
    finally:
        await delete_test_user(uid);await delete_test_user(other_uid)
