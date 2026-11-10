import asyncio
import uuid
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select,func
from langgraph.graph import StateGraph,END
from app import worker
from app.agents.state import ResearchState
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.task import ResearchTask,WorkflowRun,TaskDispatchOutbox
from app.services.provider_budget import (ProviderBudgetExceeded,increase_token_allowance,
    token_allowance_summary,reserve_provider_call,settle_provider_call)
from app.schemas.task import BudgetConfigSchema
from tests.test_provider_budget import create_running_task,delete_test_user


def usage(**kwargs):
    return {'llm_calls':3,'input_tokens':20000,'output_tokens':49000,'cost_usd':0.2,
            'active_seconds':25,'active_since':None,'reservations':{},**kwargs}


def test_extension_retains_usage_and_non_token_guards_without_changing_defaults():
    old={'max_cost_usd':0.5,'max_llm_calls':20,'timeout_seconds':900,'_provider_usage':usage()}
    new=increase_token_allowance(old,200000,100000)
    assert new['_provider_usage']==old['_provider_usage']
    assert all(new[k]==old[k] for k in ('max_cost_usd','max_llm_calls','timeout_seconds'))
    assert '_allowance_changes' not in old and len(new['_allowance_changes'])==1
    assert BudgetConfigSchema().max_output_tokens==50000 and BudgetConfigSchema().max_input_tokens==100000
    assert increase_token_allowance({},500000,50000)['max_input_tokens']==500000


@pytest.mark.parametrize('inputs,outputs',[(100000,50000),(90000,100000),(200000,49000),(500001,100000),(200000,200001)])
def test_token_changes_cannot_lower_limits_repeat_or_exceed_caps(inputs,outputs):
    with pytest.raises(ValueError):increase_token_allowance({},inputs,outputs)


@pytest.mark.parametrize('guard',[{'llm_calls':60},{'cost_usd':2.0},{'active_seconds':3600}])
def test_absolute_non_token_guards_cannot_offer_further_extension(guard):
    task=SimpleNamespace(status='NEEDS_REVIEW',current_step='BUDGET_LIMIT',completed_at=None,budget_config={'max_llm_calls':60,'timeout_seconds':3600,'_provider_usage':usage(**guard)})
    assert not token_allowance_summary(task)['can_extend']


async def stopped_task(**overrides):
    tid,uid=await create_running_task(_provider_usage=usage(**overrides))
    rid=uuid.uuid4()
    async with AsyncSessionLocal() as db:
        t=await db.get(ResearchTask,tid);t.status='NEEDS_REVIEW';t.current_step='BUDGET_LIMIT';t.worker_lease_until=None
        t.completed_at=datetime.now(timezone.utc)
        db.add(WorkflowRun(id=rid,research_task_id=tid,run_number=1,status='NEEDS_REVIEW',checkpoint_thread_id=str(uuid.uuid4())))
        await db.commit()
    return tid,uid,rid


@pytest.mark.asyncio
async def test_atomic_extension_reuses_thread_and_preserves_ledger_under_duplicate_requests():
    tid,uid,rid=await stopped_task()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+create_access_token(uid)}) as c:
            before=(await c.get(f'/api/v1/research/{tid}')).json()
            assert before['token_allowance']['can_extend']
            assert (await c.post(f'/api/v1/research/{tid}/retry')).status_code==409
            results=await asyncio.gather(*(c.post(f'/api/v1/research/{tid}/retry',json={'max_input_tokens':200000,'max_output_tokens':100000}) for _ in range(2)))
            assert sorted(r.status_code for r in results)==[202,409]
        async with AsyncSessionLocal() as db:
            t=await db.get(ResearchTask,tid);r=await db.get(WorkflowRun,rid)
            assert t.status=='QUEUED' and r.status=='RUNNING'
            assert t.budget_config['_provider_usage']==usage()
            assert t.budget_config['max_cost_usd']==2.0 and t.budget_config['max_llm_calls']==40
            assert len(t.budget_config['_allowance_changes'])==1
            assert await db.scalar(select(func.count(WorkflowRun.id)).where(WorkflowRun.research_task_id==tid))==1
            assert await db.scalar(select(func.count(TaskDispatchOutbox.id)).where(TaskDispatchOutbox.research_task_id==tid))==1
    finally:await delete_test_user(uid)


@pytest.mark.asyncio
@pytest.mark.parametrize('guard',[{'llm_calls':40},{'cost_usd':2.0},{'active_seconds':900}])
async def test_extension_rejection_rolls_back_changes_when_cost_calls_or_time_are_exhausted(guard):
    tid,uid,rid=await stopped_task(**guard)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+create_access_token(uid)}) as c:
            assert (await c.post(f'/api/v1/research/{tid}/retry',json={'max_input_tokens':200000,'max_output_tokens':100000})).status_code==409
        async with AsyncSessionLocal() as db:
            t=await db.get(ResearchTask,tid)
            assert t.status=='NEEDS_REVIEW' and t.budget_config['max_output_tokens']==50000
            assert '_allowance_changes' not in t.budget_config
            assert (await db.get(WorkflowRun,rid)).status=='NEEDS_REVIEW'
    finally:await delete_test_user(uid)


@pytest.mark.asyncio
async def test_extension_enforces_owner_and_rejects_hidden_ledger_or_money_changes():
    tid,uid,rid=await stopped_task();other,other_uid=await create_running_task()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            data={'max_input_tokens':200000,'max_output_tokens':100000}
            assert (await c.post(f'/api/v1/research/{tid}/retry',json=data)).status_code==401
            assert (await c.post(f'/api/v1/research/{tid}/retry',json=data,headers={'Authorization':'Bearer '+create_access_token(other_uid)})).status_code==404
            for extra in ({'max_cost_usd':99},{'_provider_usage':{}},{'max_llm_calls':100}):
                assert (await c.post(f'/api/v1/research/{tid}/retry',json={**data,**extra},headers={'Authorization':'Bearer '+create_access_token(uid)})).status_code==422
    finally:await delete_test_user(uid);await delete_test_user(other_uid)


@pytest.mark.asyncio
async def test_failed_step_keeps_ledger_offer_when_response_is_serialized_twice():
    from app.schemas.task import ResearchTaskResponse
    tid,uid,rid=await stopped_task()
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid);task.status='FAILED';task.current_step='WRITER'
            run=await db.get(WorkflowRun,rid);run.status='FAILED';await db.commit();await db.refresh(task)
            response=ResearchTaskResponse.model_validate(task)
            assert response.token_allowance['output_used']==49000
            assert ResearchTaskResponse.model_validate(response).token_allowance==response.token_allowance
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+create_access_token(uid)}) as c:
            response=(await c.get(f'/api/v1/research/{tid}')).json()
            assert response['token_allowance']['can_extend']
            assert response['token_allowance']['output_used']==49000
    finally:await delete_test_user(uid)


@pytest.mark.asyncio
async def test_budget_extension_resumes_postgres_checkpoint_without_repeating_research(monkeypatch):
    tid,uid=await create_running_task(_provider_usage=usage());counts={'research':0,'writer':0}
    async def research(state):counts['research']+=1;return {'current_agent':'researcher'}
    async def write(state):
        counts['writer']+=1
        reservation=await reserve_provider_call(task_id=str(tid),attempt_number=state['attempt_number'],kind='llm',model='gpt-4o-mini',input_tokens=5,output_tokens=8192)
        await settle_provider_call(task_id=str(tid),reservation_id=reservation,input_tokens=5,output_tokens=20,cost_usd=0.001,succeeded=True)
        return {'final_report_markdown':'# Checkpoint test draft\nRecorded test content.','status':'NEEDS_REVIEW'}
    def build(checkpointer=None):
        graph=StateGraph(ResearchState);graph.add_node('researcher',research);graph.add_node('writer',write)
        graph.set_entry_point('researcher');graph.add_edge('researcher','writer');graph.add_edge('writer',END)
        return graph.compile(checkpointer=checkpointer)
    monkeypatch.setattr(worker,'build_research_graph',build)
    monkeypatch.setattr(worker,'_CHECKPOINT_SCHEMA_READY',False)
    monkeypatch.setattr('app.services.task_dispatcher.dispatch_one_outbox_event',AsyncMock())
    try:
        async with AsyncSessionLocal() as db:
            t=await db.get(ResearchTask,tid);t.status='QUEUED';t.worker_lease_until=None;await db.commit()
        with pytest.raises(RuntimeError):await worker.run_langgraph_workflow(str(tid))
        async with AsyncSessionLocal() as db:
            t=await db.get(ResearchTask,tid)
            assert t.current_step=='BUDGET_LIMIT'
            run=await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id==tid));rid,thread=run.id,run.checkpoint_thread_id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+create_access_token(uid)}) as c:
            assert (await c.post(f'/api/v1/research/{tid}/retry',json={'max_input_tokens':200000,'max_output_tokens':100000})).status_code==202
        await worker.run_langgraph_workflow(str(tid))
        assert counts=={'research':1,'writer':2}
        async with AsyncSessionLocal() as db:
            run=await db.get(WorkflowRun,rid);t=await db.get(ResearchTask,tid)
            assert run.checkpoint_thread_id==thread and t.status=='NEEDS_REVIEW'
            assert t.budget_config['_provider_usage']['output_tokens']==49020
            assert t.budget_config['_provider_usage']['llm_calls']==4
    finally:await delete_test_user(uid)
