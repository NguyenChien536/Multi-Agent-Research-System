"""Legacy empty deadline errors must be explained consistently without rewriting runs."""
import httpx
import pytest

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.agent_run import AgentRun
from app.models.task import ResearchTask
from tests.test_provider_budget import create_running_task,delete_test_user


@pytest.mark.asyncio
@pytest.mark.parametrize('expired',[True,False])
async def test_workspace_and_paginated_monitor_explain_current_empty_error_without_using_old_failure(expired):
    tid,uid=await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid)
            task.status='FAILED';task.current_step='WRITER';task.attempt_number=2
            original={**task.budget_config,'_provider_usage':{'active_seconds':900.04 if expired else 1,'reservations':{}},
                '_last_failure':{'attempt_number':2,'message':None,'step':'WRITER'}}
            task.budget_config=original
            db.add(AgentRun(research_task_id=tid,agent_name='Analyst',status='FAILED',attempt_number=1,
                error_message='MODEL_INVALID_JSON: old attempt secret-value'))
            await db.commit()
        headers={'Authorization':'Bearer '+create_access_token(uid)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            detail=await c.get('/api/v1/research/'+str(tid),headers=headers)
            monitor=await c.get('/api/v1/research/'+str(tid)+'/monitor?offset=100',headers=headers)
            assert detail.status_code==monitor.status_code==200
            expected='TASK_TIME_LIMIT:' if expired else 'EXECUTION_FAILED:'
            for response in (detail,monitor):
                assert response.json()['latest_error'].startswith(expected)
                assert response.json()['failed_agent']=='WRITER'
                assert 'secret-value' not in response.text
            if expired:
                assert detail.json()['token_allowance']['can_extend'] is False
        async with AsyncSessionLocal() as db:
            assert (await db.get(ResearchTask,tid)).budget_config==original
    finally:
        await delete_test_user(uid)
