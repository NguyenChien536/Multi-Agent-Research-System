import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select
from app import worker
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.task import ResearchTask, WorkflowRun, TaskDispatchOutbox
from app.services.provider_recovery import ProviderRateLimited, rate_limit_error, can_defer
from tests.test_provider_budget import create_running_task, delete_test_user

@pytest.mark.parametrize('metadata,message,header,scope,auto', [
 ({'limit_source':'upstream_provider_shared_pool'}, 'busy', None, 'upstream', True),
 ({}, 'Daily free request limit reached', '30', 'daily', False),
 ({}, 'slow down', '12', 'rate', True),
 ({}, 'unknown limit', None, 'unknown', False),
 ({}, 'temporarily rate limited', None, 'upstream', True),
])
def test_safe_limit_classification(metadata,message,header,scope,auto):
 response=httpx.Response(429,headers={'retry-after':header} if header else {},json={'error':{'message':message,'metadata':metadata}})
 error=SimpleNamespace(status_code=429,response=response,body=response.json())
 limited=rate_limit_error(error)
 assert limited.scope==scope and limited.can_retry==auto
 assert 'busy' not in str(limited) and 'slow down' not in str(limited)


def test_deferrals_are_bounded_and_daily_or_long_waits_are_not_retried():
 rid=uuid.uuid4()
 assert can_defer(ProviderRateLimited('rate',5),{},rid)
 assert not can_defer(ProviderRateLimited('daily',5),{},rid)
 assert not can_defer(ProviderRateLimited('rate',999),{},rid)
 assert not can_defer(ProviderRateLimited('rate',5),{'_provider_recovery':{'run_id':str(rid),'count':2}},rid)
 assert rate_limit_error(RuntimeError('arbitrary 429 text')) is None

@pytest.mark.asyncio
async def test_provider_wait_releases_slot_fences_early_delivery_and_reuses_run(monkeypatch):
 tid,uid=await create_running_task()
 calls=[]
 async def graph(state):
  calls.append(True)
  if len(calls)==1:raise ProviderRateLimited('rate',30)
  return {'final_report_markdown':'# Saved paper\nComplete test fixture.','status':'COMPLETED'}
 monkeypatch.setattr(worker,'research_graph',SimpleNamespace(ainvoke=graph))
 monkeypatch.setattr('app.services.task_dispatcher.dispatch_one_outbox_event',AsyncMock())
 try:
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);t.status='QUEUED';t.worker_lease_until=None;await db.commit()
  result=await worker.run_langgraph_workflow(str(tid))
  assert result['status']=='QUEUED'
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);run=await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id==tid));run_id=run.id
   event=await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id==tid))
   assert t.worker_lease_until is None and run.status=='RUNNING'
   assert t.budget_config['_provider_usage']['active_since'] is None
   assert event.available_at>datetime.now(timezone.utc)
  assert (await worker.run_langgraph_workflow(str(tid)))['status']=='QUEUED'
  assert len(calls)==1
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);cfg=dict(t.budget_config);cfg['_provider_wait']={**cfg['_provider_wait'],'retry_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()};t.budget_config=cfg;await db.commit()
  await worker.run_langgraph_workflow(str(tid))
  async with AsyncSessionLocal() as db:
   assert len((await db.scalars(select(WorkflowRun).where(WorkflowRun.research_task_id==tid))).all())==1
   assert (await db.get(WorkflowRun,run_id)).status=='COMPLETED'
   assert (await db.get(ResearchTask,tid)).status=='COMPLETED'
 finally:await delete_test_user(uid)

@pytest.mark.asyncio
async def test_budget_block_is_visible_and_does_not_queue_another_run():
 tid,uid=await create_running_task()
 try:
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);t.status='NEEDS_REVIEW';t.current_step='BUDGET_LIMIT';await db.commit()
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+create_access_token(uid)}) as client:
   r=await client.get(f'/api/v1/research/{tid}');assert r.json()['retry_blocked_reason']=='TASK_BUDGET_LIMIT'
   r=await client.post(f'/api/v1/research/{tid}/start');assert r.status_code==409
  async with AsyncSessionLocal() as db:
   assert (await db.get(ResearchTask,tid)).status=='NEEDS_REVIEW'
   assert await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id==tid)) is None
 finally:await delete_test_user(uid)
