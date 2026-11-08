import json
import uuid

import httpx
import pytest
from fastapi import HTTPException

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.services import model_catalog
from app.services.model_connection import ModelConnectionInput, seal_connection
from app.services.user_model_settings import settings_id
from tests.test_provider_budget import create_running_task, delete_test_user

KEY = 'fake-catalog-key-not-real'
ROOT = 'https://api.groq.com/openai/v1'


def catalog_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(model_catalog.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.asyncio
async def test_catalog_uses_fixed_url_authorization_and_never_generates(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == 'GET' and str(request.url) == ROOT+'/models'
        assert request.headers['authorization'] == 'Bearer '+KEY
        return httpx.Response(200, json={'data':[{'id':'chat-fixture'}, {'id':'embedding-fixture'}, {'id':KEY}, None]})
    catalog_transport(monkeypatch,handler)
    result = await model_catalog.discover_models(ROOT,KEY)
    assert result['models']==[{'id':'chat-fixture','free':None,'supports_json_schema':False}]
    assert result['generation_calls']==0 and len(requests)==1
    assert KEY not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('status,category',[(401,'PROVIDER_AUTH_FAILED'),(403,'PROVIDER_AUTH_FAILED'),(404,'MODEL_CATALOG_UNAVAILABLE'),(429,'PROVIDER_RATE_LIMIT'),(503,'PROVIDER_UNAVAILABLE'),(302,'EXECUTION_FAILED')])
async def test_catalog_errors_never_echo_body_or_follow_redirects(monkeypatch,status,category):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status,text=KEY,headers={'location':'https://example.com/leak'})
    catalog_transport(monkeypatch,handler)
    with pytest.raises(HTTPException) as error:
        await model_catalog.discover_models(ROOT,KEY)
    assert category in error.value.detail and KEY not in error.value.detail
    assert len(calls)==1


@pytest.mark.asyncio
async def test_free_catalog_filters_paid_models_and_keeps_router(monkeypatch):
    def handler(_):
        return httpx.Response(200,json={'data':[
            {'id':'test/paid','pricing':{'prompt':'1','completion':'1'}},
            {'id':'test/chat:free','pricing':{'prompt':'0','completion':'0'}},
        ]})
    catalog_transport(monkeypatch,handler)
    result=await model_catalog.discover_models('https://openrouter.ai/api/v1',KEY)
    assert [model['id'] for model in result['models']]==['openrouter/free','test/chat:free']


@pytest.mark.asyncio
async def test_free_router_keeps_advertised_schema_capability(monkeypatch):
    catalog_transport(monkeypatch,lambda _:httpx.Response(200,json={'data':[
        {'id':'openrouter/free','pricing':{'prompt':'0','completion':'0'},'supported_parameters':['response_format','structured_outputs']}
    ]}))
    result=await model_catalog.discover_models('https://openrouter.ai/api/v1',KEY)
    assert result['models']==[{'id':'openrouter/free','free':True,'supports_json_schema':True}]


@pytest.mark.asyncio
async def test_google_resource_names_become_completion_model_ids(monkeypatch):
    def handler(_):
        return httpx.Response(200,json={'data':[{'id':'models/gemini-test-flash'}, {'id':'models/lyria-test'}, {'id':'models/gemini-test-image'}]})
    catalog_transport(monkeypatch,handler)
    result=await model_catalog.discover_models('https://generativelanguage.googleapis.com/v1beta/openai',KEY)
    assert result['models']==[{'id':'gemini-test-flash','free':None,'supports_json_schema':False}]


@pytest.mark.asyncio
async def test_catalog_endpoint_reuses_only_owned_saved_key_and_validates_service(monkeypatch):
    tid,uid=await create_running_task()
    other_tid,other_uid=await create_running_task()
    value=ModelConnectionInput(api_key=KEY,base_url=ROOT,model='chat-fixture')
    calls=[]
    async def discover(root,key,free_only):
        calls.append((root,key,free_only))
        return {'models':[{'id':'chat-fixture','free':None,'supports_json_schema':False}],'generation_calls':0,'check':'catalog_only_not_generation_or_quota'}
    monkeypatch.setattr(model_catalog,'discover_models',discover)
    try:
        async with AsyncSessionLocal() as db:
            (await db.get(User,uid)).model_connection=seal_connection(value,settings_id(uid),uid)
            await db.commit()
        headers={'Authorization':'Bearer '+create_access_token(uid)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            path='/api/v1/settings/model-connection/models'
            assert (await client.post(path,json={'base_url':ROOT})).status_code==401
            response=await client.post(path,json={'base_url':ROOT},headers=headers)
            assert response.status_code==200 and KEY not in response.text
            assert calls==[(ROOT,KEY,True)]
            assert (await client.post(path,json={'base_url':ROOT,'task_id':str(other_tid)},headers=headers)).status_code==404
            assert (await client.post(path,json={'base_url':'http://127.0.0.1:8080','api_key':KEY},headers=headers)).status_code==422
            assert len(calls)==1
    finally:
        await delete_test_user(uid)
        await delete_test_user(other_uid)
