"""Large advertised completions must not bypass the article budget or wire cap."""
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.agents.nodes import BudgetedFallbackLLM, invoke_llm_with_budget
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.schemas.model_settings import ConnectionUpdate
from app.services import model_catalog
from app.services.model_connection import ModelConnectionInput, build_connection_client, async_connection_scope, current_connection, seal_connection
from app.services.provider_budget import ProviderBudgetExceeded, personal_output_capacity, reserve_provider_call, token_allowance_summary
from tests.test_model_catalog import catalog_transport
from tests.test_provider_budget import create_running_task, delete_test_user

ROOT = 'https://openrouter.ai/api/v1'
KEY = 'fake-capacity-key-not-real'


def test_settings_accept_large_catalog_limits_but_reject_unbounded_values():
    value = dict(api_key=KEY,base_url=ROOT,model='fixture/max:free',output_token_limit=460800)
    assert ModelConnectionInput(**value).output_token_limit == 460800
    assert ConnectionUpdate(**value).output_token_limit == 460800
    with pytest.raises(ValidationError):
        ModelConnectionInput(**{**value,'output_token_limit':1000001})


@pytest.mark.asyncio
async def test_free_catalog_orders_by_output_not_context_and_keeps_unknown_limits_unknown(monkeypatch):
    catalog_transport(monkeypatch,lambda _:httpx.Response(200,json={'data':[
        {'id':'fixture/long-context:free','context_length':1000000,'pricing':{'prompt':'0','completion':'0'},'top_provider':{'max_completion_tokens':8192}},
        {'id':'fixture/large-output:free','context_length':512000,'pricing':{'prompt':'0','completion':'0'},'top_provider':{'max_completion_tokens':460800},'supported_parameters':['structured_outputs']},
        {'id':'fixture/unknown:free','pricing':{'prompt':'0','completion':'0'},'top_provider':'untrusted'},
        {'id':'fixture/paid','pricing':{'prompt':'1','completion':'2'},'top_provider':{'max_completion_tokens':900000}},
    ]}))
    result=await model_catalog.discover_models(ROOT,KEY)
    assert [r['id'] for r in result['models']][:2] == ['fixture/large-output:free','fixture/long-context:free']
    assert result['models'][0]['max_output_tokens'] == 460800
    assert not any(r['id']=='fixture/paid' for r in result['models'])
    assert 'max_output_tokens' not in next(r for r in result['models'] if r['id']=='fixture/unknown:free')


@pytest.mark.asyncio
async def test_output_preview_subtracts_usage_and_in_flight_reservations_without_resetting():
    tid,uid=await create_running_task()
    try:
        await reserve_provider_call(task_id=tid,attempt_number=1,kind='llm',model='gpt-4o-mini',output_tokens=10000)
        assert await personal_output_capacity(tid,460800) == 40000
        assert await personal_output_capacity(tid,8192) == 8192
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            config={**task.budget_config}; usage={**config['_provider_usage']}
            usage['output_tokens']=39500
            task.budget_config={**config,'_provider_usage':usage}; await db.commit()
        with pytest.raises(ProviderBudgetExceeded):
            await personal_output_capacity(tid,460800)
    finally:
        await delete_test_user(uid)


@pytest.mark.asyncio
@pytest.mark.parametrize('structured,truncated_first', [(False,False),(True,False),(True,True)])
async def test_large_limit_is_clamped_on_real_wire_and_reservation_for_each_attempt(structured,truncated_first):
    tid,uid=await create_running_task()
    class Answer(BaseModel):
        answer: str
    value=ModelConnectionInput(api_key=KEY,base_url=ROOT,model='fixture/max:free',output_token_limit=460800,
        structured_output_mode='json_schema',reasoning_effort='none')
    config={'_llm_connection':seal_connection(value,tid,uid)}
    seen=[]
    def handler(request):
        body=json.loads(request.content); seen.append(body)
        cut_off = truncated_first and len(seen)==1
        assert body.get('max_completion_tokens',body.get('max_tokens')) == (32768 if len(seen)==2 else 16384)
        assert body['provider']['max_price']['completion'] == 0
        if structured: assert body['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'id':'capacity-fixture','object':'chat.completion','created':1,'model':'fixture/max:free',
            'choices':[{'index':0,'message':{'role':'assistant','content':'{"answer":"ok"}'},'finish_reason':'length' if cut_off else 'stop'}],
            'usage':{'prompt_tokens':100,'completion_tokens':16384 if cut_off else 12,'total_tokens':16484 if cut_off else 112}})
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid); task.budget_config={**task.budget_config,**config}; await db.commit()
        async with async_connection_scope(config,tid,uid):
            connection=current_connection()
            client=build_connection_client(connection)
            await client.http_async_client.aclose()
            transport=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            client.http_async_client=transport
            client.root_async_client._client=transport
            llm=BudgetedFallbackLLM([(connection.model_tag,client)])
            if structured: llm=llm.with_structured_output(Answer)
            result=await invoke_llm_with_budget({'task_id':str(tid),'attempt_number':1,'enforce_provider_budget':True},llm,
                [HumanMessage(content='Reply with answer ok')],model_name=connection.model_tag)
            if structured: assert result.answer=='ok'
        assert len(seen)==(2 if truncated_first else 1)
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid); usage=task.budget_config['_provider_usage']
            assert usage['output_tokens']==(16396 if truncated_first else 12)
            assert usage['llm_calls']==len(seen) and not usage['reservations']
            assert task.budget_config['max_output_tokens']==50000
    finally:
        await delete_test_user(uid)


def test_maximum_model_ceiling_does_not_offer_token_extension_when_a_normal_group_fits():
    from types import SimpleNamespace
    task=SimpleNamespace(status='FAILED',current_step='WRITER',completed_at=None,budget_config={
        '_llm_connection':{'profile':{'output_token_limit':460800}},'max_output_tokens':50000})
    assert token_allowance_summary(task)['can_extend'] is False
    task.budget_config['_provider_usage']={'output_tokens':40000,'reservations':{}}
    assert token_allowance_summary(task)['can_extend'] is True
