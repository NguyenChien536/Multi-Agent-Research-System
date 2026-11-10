"""Owner-approved free routing and durable waits, without real provider calls."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.agents.nodes import BudgetedFallbackLLM
from app.services.model_connection import (ModelConnectionInput, ModelConnection, build_connection_client,
    temporary_connection_scope, seal_connection, open_connection, remember_response_model)
from app.services.provider_recovery import ProviderRateLimited, rate_limit_error, retry_delay

ROOT='https://openrouter.ai/api/v1'


def connection_input(**changes):
    return ModelConnectionInput(api_key='fake-fallback-key-only',base_url=ROOT,model='fixture/primary:free',
        **{'fallback_models':['fixture/backup:free'],'structured_output_mode':'json_schema',**changes})


@pytest.mark.parametrize('changes',[
    {'fallback_models':['paid/model']},
    {'fallback_models':['openrouter/auto']},
    {'input_price_per_million':1},
    {'base_url':'https://api.groq.com/openai/v1'},
    {'fallback_models':['fixture/x:free']*4},
])
def test_fallbacks_cannot_enable_paid_or_cross_provider_requests(changes):
    values={'api_key':'fake-key-only','base_url':ROOT,'model':'fixture/primary:free',
        'fallback_models':['fixture/backup:free'],**changes}
    with pytest.raises(ValidationError):ModelConnectionInput(**values)


def test_routing_is_encrypted_owner_bound_and_primary_not_duplicated():
    value=connection_input(fallback_models=['fixture/primary:free','fixture/backup:free','fixture/backup:free'])
    assert value.fallback_models==['fixture/backup:free']
    stored=seal_connection(value,'task','owner')
    restored=open_connection({'_llm_connection':stored},'task','owner')
    assert restored.fallback_models==['fixture/backup:free']
    with pytest.raises(ValueError):open_connection({'_llm_connection':stored},'task','other-owner')
    assert 'fake-fallback-key' not in json.dumps(stored)


@pytest.mark.asyncio
async def test_actual_http_body_keeps_free_guards_and_format_retry_can_change_model():
    value=connection_input()
    connection=ModelConnection(**value.model_dump(exclude={'api_key'}),api_key=value.api_key.get_secret_value())
    seen=[]
    class Answer(BaseModel):answer:str
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert body['provider']['require_parameters']
        assert body['provider']['max_price']=={'prompt':0,'completion':0,'request':0}
        assert body['response_format']['type']=='json_schema'
        assert body['route']=='fallback'
        if len(seen)==1:
            assert body['model']=='fixture/primary:free' and body['models']==['fixture/backup:free']
        else:
            assert body['model']=='fixture/backup:free' and body['models']==['fixture/primary:free']
        return httpx.Response(200,json={'id':'fixture','object':'chat.completion','created':1,'model':body['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':'not JSON' if len(seen)==1 else '{"answer":"recorded"}'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':8,'total_tokens':18}})
    async with temporary_connection_scope(connection):
        model=build_connection_client(connection)
        await model.http_async_client.aclose()
        transport=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        model.http_async_client=transport;model.root_async_client._client=transport
        chain=BudgetedFallbackLLM([(connection.model_tag,model)]).with_structured_output(Answer)
        result=await chain.ainvoke([HumanMessage(content='Return answer recorded')])
        assert result.answer=='recorded' and len(seen)==2
        assert connection.last_response_model=='fixture/backup:free'
        assert connection.model=='fixture/primary:free'
        remember_response_model(SimpleNamespace(response_metadata={'model_name':'sk-private-content'}))
        assert connection.last_response_model is None
    assert transport.is_closed


def test_unknown_429_can_wait_but_a_text_mention_cannot_trigger_retries():
    error=httpx.HTTPStatusError('private',request=httpx.Request('GET',ROOT),response=httpx.Response(429))
    wrapped=RuntimeError('gateway failed');wrapped.__cause__=error
    limited=rate_limit_error(wrapped)
    assert limited.can_retry and limited.scope=='unknown'
    assert rate_limit_error(RuntimeError('429 in an unrelated exception')) is None


def test_reset_header_is_interpreted_as_epoch_milliseconds():
    reset_at=datetime.now(timezone.utc).timestamp()+90
    response=httpx.Response(429,headers={'x-ratelimit-reset':str(int(reset_at*1000))},json={'error':{'message':'Rate limit exceeded'}})
    error=rate_limit_error(SimpleNamespace(status_code=429,response=response,body=response.json()))
    assert error is not None and error.can_retry
    assert 85<=error.retry_after<=95


def test_wait_uses_retry_after_and_exponential_backoff_without_tight_loop():
    now=datetime(2026,11,10,4,tzinfo=timezone.utc)
    error=ProviderRateLimited('rate',1200)
    assert retry_delay(error,5,now=now)==1200
    error=ProviderRateLimited('unknown')
    first=retry_delay(error,1,now=now,task_id='task')
    second=retry_delay(error,2,now=now,task_id='task')
    assert 60<=first<=75 and 120<=second<=135
    assert 3600<=retry_delay(error,50,now=now,task_id='task')<=3615


def test_openrouter_daily_limit_waits_until_next_utc_day():
    now=datetime(2026,11,10,4,tzinfo=timezone.utc)
    delay=retry_delay(ProviderRateLimited('daily'),1,now=now,base_url=ROOT)
    assert delay==20*3600+5


@pytest.mark.asyncio
async def test_daily_wait_is_durable_and_can_be_cancelled_without_reentry(monkeypatch):
    from unittest.mock import AsyncMock
    from sqlalchemy import select
    from app import worker
    from app.main import app
    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token
    from app.models.task import ResearchTask, WorkflowRun, TaskDispatchOutbox
    from tests.test_provider_budget import create_running_task,delete_test_user
    tid,uid=await create_running_task()
    calls=[]
    async def graph(state):
        calls.append(True)
        raise ProviderRateLimited('daily')
    monkeypatch.setattr(worker,'research_graph',SimpleNamespace(ainvoke=graph))
    monkeypatch.setattr('app.services.task_dispatcher.dispatch_one_outbox_event',AsyncMock())
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            task.status='QUEUED';task.worker_lease_until=None
            task.budget_config={**task.budget_config,'_llm_connection':seal_connection(connection_input(),tid,uid)}
            await db.commit()
        result=await worker.run_langgraph_workflow(str(tid))
        assert result['status']=='QUEUED'
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            wait=task.budget_config['_provider_wait']
            assert wait['reason']=='PROVIDER_DAILY_LIMIT'
            assert task.worker_lease_until is None
            assert task.budget_config['_provider_usage']['active_since'] is None
            event=await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id==tid))
            assert event.available_at==datetime.fromisoformat(wait['retry_at'])
            assert len((await db.scalars(select(WorkflowRun).where(WorkflowRun.research_task_id==tid))).all())==1
        assert (await worker.run_langgraph_workflow(str(tid)))['status']=='QUEUED'
        assert len(calls)==1
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post(f'/api/v1/research/{tid}/cancel',headers={'Authorization':'Bearer '+create_access_token(uid)})
            assert response.status_code==200
        await worker.run_langgraph_workflow(str(tid))
        assert len(calls)==1
    finally:
        await delete_test_user(uid)
