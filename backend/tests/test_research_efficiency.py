"""Regression checks for request classification, context and explicit recovery."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import SystemMessage

from app.services.public_errors import public_error, provider_failure_message, provider_request_rejected
from app.services.sectional_writer import group_output_tokens, prior_section_context
from app.services.structured_output import compact_prompt_schema
from app.services.provider_budget import HARD_MAX_LLM_CALLS, increase_token_allowance, token_allowance_summary


def test_legacy_invalid_request_is_not_mislabelled_as_quota():
    raw = 'Your API connection failed (OpenAIInvalidRequestError). Check its key, model, quota and supported output format.'
    safe = public_error(raw)
    assert safe.startswith('PROVIDER_REQUEST_INVALID:')
    assert public_error(safe) == safe


@pytest.mark.parametrize('code,expected', [(400,'REQUEST_INVALID'),(422,'REQUEST_INVALID'),
    (401,'AUTH_FAILED'),(403,'AUTH_FAILED'),(404,'MODEL_NOT_FOUND'),(429,'RATE_LIMIT')])
def test_typed_rejections_keep_actual_status_and_hide_body(code, expected):
    error = RuntimeError('private key and quota wording must never decide this status')
    error.status_code = code
    wrapper = RuntimeError('gateway failed')
    wrapper.__cause__ = error
    assert provider_failure_message(wrapper).startswith('PROVIDER_'+expected+':')
    assert 'private key' not in provider_failure_message(wrapper)
    assert provider_request_rejected(wrapper)


def test_timeout_is_not_a_zero_usage_explicit_rejection():
    assert not provider_request_rejected(TimeoutError('no response'))
    assert provider_failure_message(TimeoutError('no response')) is None
    error=type('BadRequestError',(RuntimeError,),{})('upstream failed')
    error.status_code=503
    assert not provider_request_rejected(error)
    assert provider_failure_message(error) is None


@pytest.mark.asyncio
async def test_paid_openrouter_requires_compatible_endpoints_without_free_only_routing():
    from app.services.model_connection import ModelConnection, build_connection_client
    connection=ModelConnection(base_url='https://openrouter.ai/api/v1',model='google/gemini-2.5-flash',
        api_key='fake-test-only-key',input_price_per_million=.3,output_price_per_million=2.5)
    client=build_connection_client(connection)
    try:
        assert client.extra_body['provider']=={'require_parameters':True}
        assert 'max_price' not in client.extra_body['provider']
    finally:
        await connection.aclose()


def test_compact_schema_keeps_domain_title_and_validation():
    schema = {'title':'Display metadata','type':'object','properties':{
        'title':{'type':'string','title':'Display title','maxLength':20},
        'examples':{'type':'array','items':{'type':'string'}}},'required':['title']}
    compact = compact_prompt_schema(schema)
    assert 'title' not in compact
    assert set(compact['properties']) == {'title','examples'}
    assert compact['properties']['title'] == {'type':'string','maxLength':20}
    assert schema['title'] == 'Display metadata'


@pytest.mark.asyncio
async def test_a_previous_small_allocation_does_not_shrink_the_next_request(monkeypatch):
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage, HumanMessage
    from app.agents import nodes
    from app.services.model_connection import ModelConnection
    connection=ModelConnection(base_url='https://openrouter.ai/api/v1',model='fixture:free',
        api_key='fake-key-only',input_price_per_million=0,output_price_per_million=0,output_token_limit=16384)
    monkeypatch.setattr('app.services.model_connection.current_connection',lambda:connection)
    model=SimpleNamespace(max_tokens=1024,ainvoke=AsyncMock(return_value=AIMessage(content='ok')))
    reserve=AsyncMock(return_value='reservation')
    monkeypatch.setattr(nodes,'reserve_provider_call',reserve)
    monkeypatch.setattr(nodes,'settle_provider_call',AsyncMock())
    monkeypatch.setattr('app.services.provider_budget.personal_output_capacity',AsyncMock(side_effect=lambda _,cap:cap))
    monkeypatch.setattr('app.services.provider_budget.assert_task_active',AsyncMock())
    chain=nodes.BudgetedFallbackLLM([(connection.model_tag,model)],output_limits={connection.model_tag:1024})
    await nodes.invoke_llm_with_budget({'task_id':'test-task','attempt_number':1,'enforce_provider_budget':True},chain,
        [HumanMessage(content='Write the next group')],model_name=connection.model_tag,output_tokens=8192)
    assert reserve.await_args.kwargs['output_tokens']==8192
    assert model.max_tokens==8192


@pytest.mark.asyncio
async def test_invalid_request_is_not_retried_as_json_or_quota(monkeypatch):
    from unittest.mock import AsyncMock
    from app.agents import nodes
    from app.services.public_errors import ProviderRequestRejected
    error=RuntimeError('private provider body mentions quota')
    error.status_code=400
    model=SimpleNamespace(max_tokens=4096,ainvoke=AsyncMock(side_effect=error))
    settled=AsyncMock()
    monkeypatch.setattr(nodes,'reserve_provider_call',AsyncMock(return_value='reservation'))
    monkeypatch.setattr(nodes,'settle_provider_call',settled)
    monkeypatch.setattr('app.services.provider_budget.personal_output_capacity',AsyncMock(side_effect=lambda _,cap:cap))
    monkeypatch.setattr('app.services.provider_budget.assert_task_active',AsyncMock())
    chain=nodes.BudgetedFallbackLLM([('byok:fixture',model)])
    with pytest.raises(ProviderRequestRejected,match='PROVIDER_REQUEST_INVALID'):
        await nodes.invoke_llm_with_budget({'task_id':'test-task','enforce_provider_budget':True},chain,[],model_name='byok:fixture')
    assert model.ainvoke.await_count==1
    assert settled.await_args.kwargs['rejected']
    assert settled.await_args.kwargs['output_tokens']==0


def test_group_context_reduces_repeated_body_but_abstract_reads_full_text():
    sections = {'Methods':'### Input\n'+('measured procedure ' * 1200),
                'Results':'### Outcome\n'+('recorded result ' * 900)}
    compact = prior_section_context(sections)
    full = prior_section_context(sections,full_text=True)
    assert len(compact) < len(full) / 5
    assert all(name in compact for name in sections)
    assert 'Input' in compact and 'Outcome' in compact
    assert 'excerpt' in compact
    assert all(body in full for body in sections.values())
    assert sections['Methods'].count('measured procedure') == 1200


def test_group_output_capacity_matches_group_not_whole_paper():
    assert group_output_tokens([SystemMessage(content='Aim for approximately 200 words')],16384) == 4096
    assert group_output_tokens([SystemMessage(content='Aim for approximately 800 words')],16384) == 5248
    assert group_output_tokens([SystemMessage(content='Aim for approximately 800 words')],2048) == 2048
    assert group_output_tokens([],8192) == 8192


@pytest.mark.parametrize('used_calls,used_seconds', [(40,100),(3,900),(40,900)])
def test_exhausted_time_or_calls_can_extend_without_reset_or_higher_cost(used_calls,used_seconds):
    config = {'max_cost_usd':.5,'max_llm_calls':40,'timeout_seconds':900,
              'max_input_tokens':100000,'max_output_tokens':50000,
              '_provider_usage':{'llm_calls':used_calls,'active_seconds':used_seconds,
                 'cost_usd':.1,'input_tokens':1000,'output_tokens':1000,'reservations':{}}}
    task = SimpleNamespace(status='FAILED',current_step='WRITER',completed_at=None,budget_config=config)
    summary = token_allowance_summary(task)
    assert summary['can_extend']
    extended = increase_token_allowance(config,summary['next_input_tokens'],summary['next_output_tokens'],
        max_llm_calls=summary['next_max_llm_calls'],timeout_seconds=summary['next_timeout_seconds'])
    assert extended['_provider_usage'] == config['_provider_usage']
    assert extended['max_cost_usd'] == config['max_cost_usd'] == .5
    assert extended['max_llm_calls'] == (50 if used_calls==40 else 40)
    assert extended['timeout_seconds'] == (1800 if used_seconds==900 else 900)
    assert config['timeout_seconds'] == 900


def test_spent_cost_and_absolute_resource_caps_cannot_offer_unsafe_resume():
    task = SimpleNamespace(status='FAILED',current_step='BUDGET_LIMIT',completed_at=None,budget_config={
        'max_cost_usd':.5,'_provider_usage':{'cost_usd':.5,'reservations':{}}})
    assert not token_allowance_summary(task)['can_extend']
    with pytest.raises(ValueError):
        increase_token_allowance({},100000,50000,max_llm_calls=HARD_MAX_LLM_CALLS + 1)
    with pytest.raises(ValueError):
        increase_token_allowance({},100000,50000,timeout_seconds=3601)


@pytest.mark.asyncio
async def test_paid_probe_requires_explicit_consent_and_uses_nested_schema(monkeypatch):
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from app.services import model_connection_check as checks
    from app.services.model_connection import ModelConnectionInput
    monkeypatch.setattr(checks,'discover_models',AsyncMock(return_value={'models':[{'id':'gemini-fixture'}]}))
    seen = []
    class Model:
        extra_body = {}
        def bind(self,**kwargs):
            seen.append(kwargs['extra_body'])
            return RunnableLambda(lambda _:AIMessage(content='{"ok":true,"findings":[{"step":"review","supported":true,"note":"fixture"}]}'))
    def build(connection):
        assert connection.output_token_limit == 2048
        return Model()
    monkeypatch.setattr(checks,'build_connection_client',build)
    value=ModelConnectionInput(api_key='fake-private-test-key',model='gemini-fixture',
        base_url='https://generativelanguage.googleapis.com/v1beta/openai',
        input_price_per_million=.3,output_price_per_million=2.5,structured_output_mode='json_schema')
    blocked=await checks.check_connection(value,generate=True)
    assert blocked['status']=='paid_probe_confirmation_required' and blocked['generation_calls']==0
    assert not seen
    result=await checks.check_connection(value,generate=True,paid_probe_confirmed=True)
    assert result['status']=='ok' and result['generation_calls']==1
    schema=seen[0]['response_format']['json_schema']['schema']
    assert 'findings' in schema['properties']
    assert 'maxItems' not in schema['properties']['findings']
    assert 'fake-private' not in str(result)


@pytest.mark.asyncio
async def test_explicit_time_extension_requeues_same_run_and_preserves_ledger():
    import httpx
    from app.main import app
    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token
    from app.models.task import ResearchTask, WorkflowRun
    from tests.test_token_allowance import stopped_task
    from tests.test_provider_budget import delete_test_user
    tid,uid,rid=await stopped_task(active_seconds=900)
    try:
        async with AsyncSessionLocal() as db:
            before=dict((await db.get(ResearchTask,tid)).budget_config['_provider_usage'])
            thread=(await db.get(WorkflowRun,rid)).checkpoint_thread_id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post(f'/api/v1/research/{tid}/retry',
                headers={'Authorization':'Bearer '+create_access_token(uid)},
                json={'max_input_tokens':100000,'max_output_tokens':50000,'timeout_seconds':1800})
            assert response.status_code==202
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            assert task.status=='QUEUED' and task.budget_config['timeout_seconds']==1800
            assert task.budget_config['_provider_usage']==before
            assert task.budget_config['max_cost_usd']==2
            assert (await db.get(WorkflowRun,rid)).checkpoint_thread_id==thread
    finally:
        await delete_test_user(uid)
