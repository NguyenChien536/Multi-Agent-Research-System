"""Regression coverage for visible failures and bounded provider retry semantics."""
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.agents import nodes
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.task import ResearchTask
from app.models.agent_run import AgentRun
from app.services.public_errors import ProviderUnavailable, public_error
from tests.test_provider_budget import create_running_task, delete_test_user


@pytest.mark.asyncio
async def test_latest_failure_is_owned_current_attempt_and_redacted():
    tid, uid = await create_running_task()
    other_tid, other_uid = await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, tid)
            task.status = 'FAILED'
            task.attempt_number = 2
            db.add_all([
                AgentRun(research_task_id=tid, agent_name='Writer', status='FAILED', attempt_number=1, error_message='401 old-key'),
                AgentRun(research_task_id=tid, agent_name='Methodologist', status='FAILED', attempt_number=2,
                    error_message='503 UNAVAILABLE fake-test-secret-not-real high demand'),
            ])
            await db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get(f'/api/v1/research/{tid}')).status_code == 401
            assert (await client.get(f'/api/v1/research/{tid}', headers={'Authorization':'Bearer '+create_access_token(other_uid)})).status_code == 404
            response = await client.get(f'/api/v1/research/{tid}', headers={'Authorization':'Bearer '+create_access_token(uid)})
            assert response.status_code == 200
            assert response.json()['latest_error'].startswith('PROVIDER_UNAVAILABLE:')
            assert response.json()['failed_agent'] == 'Methodologist'
            assert 'fake-test-secret' not in response.text and 'old-key' not in response.text
    finally:
        await delete_test_user(uid)
        await delete_test_user(other_uid)


@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected_calls', [(503,2), (401,1), (429,1), (404,1)])
async def test_transient_retry_is_bounded_and_never_retries_bad_keys_or_quota(monkeypatch,status,expected_calls):
    calls = []
    class Failure(RuntimeError):
        status_code = status
    async def failing(_):
        calls.append(True)
        raise Failure(str(status))
    async def no_wait(_): pass
    monkeypatch.setattr(nodes.asyncio, 'sleep', no_wait)
    with pytest.raises((ProviderUnavailable, RuntimeError)):
        await nodes.BudgetedFallbackLLM([('byok:fixture',SimpleNamespace(ainvoke=failing))]).ainvoke([])
    assert len(calls) == expected_calls


@pytest.mark.asyncio
async def test_recovered_transient_response_is_not_reported_as_failure(monkeypatch):
    calls = []
    async def overloaded_then_ok(_):
        calls.append(True)
        if len(calls)==1: raise RuntimeError('503 UNAVAILABLE')
        return SimpleNamespace(content='ok')
    async def no_wait(_): pass
    monkeypatch.setattr(nodes.asyncio,'sleep',no_wait)
    result = await nodes.BudgetedFallbackLLM([('byok:fixture',SimpleNamespace(ainvoke=overloaded_then_ok))]).ainvoke([])
    assert result.content == 'ok' and len(calls)==2


def test_public_errors_do_not_expose_provider_bodies():
    for raw in ['503 high demand SECRET', '404 model_not_found SECRET', '403 PERMISSION_DENIED SECRET']:
        assert 'SECRET' not in public_error(raw)
    for raw in ['401 invalid key', '429 quota', '503 high demand', '404 model_not_found', 'timeout', 'budget', 'MODEL_INVALID_JSON', 'unknown failure']:
        assert public_error(public_error(raw)) == public_error(raw)


@pytest.mark.asyncio
async def test_initialization_failure_is_visible_without_an_agent_run():
    tid,uid=await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            task.status='FAILED'
            task.budget_config={**task.budget_config,'_last_failure':{
                'attempt_number':task.attempt_number,'message':'PROVIDER_AUTH_FAILED: Provider rejected authentication.'}}
            await db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.get(f'/api/v1/research/{tid}',headers={'Authorization':'Bearer '+create_access_token(uid)})
            assert response.status_code==200 and response.json()['latest_error'].startswith('PROVIDER_AUTH_FAILED:')
    finally:
        await delete_test_user(uid)


@pytest.mark.asyncio
async def test_retry_preserves_run_plan_and_usage_but_rejects_duplicate_or_other_owner():
    from app.models.task import WorkflowRun, TaskDispatchOutbox
    from sqlalchemy import select
    tid, uid = await create_running_task()
    _, other_uid = await create_running_task()
    run_id, thread = uuid.uuid4(), str(uuid.uuid4())
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            task.status='FAILED'
            task.plan={'search_queries':['preserved query']}
            task.plan_version=3
            task.total_tokens_used=120
            db.add(WorkflowRun(id=run_id,research_task_id=tid,run_number=1,status='FAILED',checkpoint_thread_id=thread,plan_version=3))
            await db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            path=f'/api/v1/research/{tid}/retry'
            headers={'Authorization':'Bearer '+create_access_token(uid)}
            assert (await client.post(path)).status_code==401
            assert (await client.post(path,headers={'Authorization':'Bearer '+create_access_token(other_uid)})).status_code==404
            assert (await client.post(path,headers=headers)).status_code==202
            assert (await client.post(path,headers=headers)).status_code==409
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            run=await db.get(WorkflowRun,run_id)
            assert task.status=='QUEUED' and task.plan_version==3
            assert task.plan['search_queries']==['preserved query'] and task.total_tokens_used==120
            assert run.status=='RUNNING' and run.checkpoint_thread_id==thread
            assert await db.scalar(select(TaskDispatchOutbox.id).where(TaskDispatchOutbox.research_task_id==tid))
    finally:
        await delete_test_user(uid)
        await delete_test_user(other_uid)
