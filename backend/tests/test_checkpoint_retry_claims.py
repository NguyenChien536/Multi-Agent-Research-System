"""Repeated claims must preserve the failed node, evidence and interrupt decisions."""
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.errors import InvalidUpdateError

from app import worker
from app.agents.state import ResearchState
from app.core.config import settings


@asynccontextmanager
async def saver(kind):
    if kind == 'memory':
        yield InMemorySaver()
    else:
        async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as store:
            await store.setup()
            yield store


@pytest.mark.asyncio
@pytest.mark.parametrize('persistence',['memory','postgres'])
@pytest.mark.parametrize('first_node_fails',[False,True])
async def test_three_failures_then_success_resume_only_failed_node(persistence,first_node_fails):
    prepared,attempts=[],[]
    task=SimpleNamespace(id=uuid.uuid4())
    run=SimpleNamespace(id=uuid.uuid4(),checkpoint_thread_id=str(uuid.uuid4()))
    async def prepare(state):
        prepared.append(True)
        return {'collected_sources':[{'source_tag':'preserved-source'}]}
    async def work(state):
        attempts.append(state['attempt_number'])
        if len(attempts)<4: raise RuntimeError('controlled provider failure')
        return {'final_report_markdown':'# Preserved draft','status':'NEEDS_REVIEW'}
    builder=StateGraph(ResearchState)
    builder.add_node('prepared',prepare);builder.add_node('work',work)
    builder.add_edge(START,'work' if first_node_fails else 'prepared')
    builder.add_edge('prepared','work');builder.add_edge('work',END)
    async with saver(persistence) as store:
        graph=builder.compile(checkpointer=store)
        for attempt in (1,2,3,4):
            state={'task_id':str(task.id),'workflow_run_id':str(run.id),'attempt_number':attempt,
                'report_length':'MEDIUM','citation_style':'APA','max_sources':12,'enforce_provider_budget':False}
            if attempt<4:
                with pytest.raises(RuntimeError,match='controlled provider failure'):
                    await worker._invoke_checkpointed_graph_unchecked(graph,state,task,run,None)
            else:
                result,_=await worker._invoke_checkpointed_graph_unchecked(graph,state,task,run,None)
                assert result['attempt_number']==4 and result['final_report_markdown']=='# Preserved draft'
                assert len(result.get('collected_sources',[]))==(0 if first_node_fails else 1)
        assert attempts==[1,2,3,4] and len(prepared)==(0 if first_node_fails else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize('persistence',['memory','postgres'])
async def test_legacy_pending_command_writes_are_replaced_without_replaying_work(persistence):
    prepared,attempts=[],[]
    ready=False
    task=SimpleNamespace(id=uuid.uuid4())
    run=SimpleNamespace(id=uuid.uuid4(),checkpoint_thread_id=str(uuid.uuid4()))
    async def prepare(_):
        prepared.append(True)
        return {'claims':[{'claim_id':'retained-evidence'}]}
    async def work(state):
        attempts.append(state['attempt_number'])
        if not ready: raise RuntimeError('controlled failure')
        return {'final_report_markdown':'# Recovered'}
    builder=StateGraph(ResearchState)
    builder.add_node('prepared',prepare);builder.add_node('work',work)
    builder.add_edge(START,'prepared');builder.add_edge('prepared','work');builder.add_edge('work',END)
    async with saver(persistence) as store:
        graph=builder.compile(checkpointer=store)
        config={'configurable':{'thread_id':run.checkpoint_thread_id}}
        initial={'task_id':str(task.id),'workflow_run_id':str(run.id),'attempt_number':1,
            'report_length':'MEDIUM','citation_style':'APA','max_sources':12,'enforce_provider_budget':False}
        with pytest.raises(RuntimeError,match='controlled failure'): await graph.ainvoke(initial,config=config)
        # Reproduce the legacy worker's repeated Command(update=...) inputs.
        for attempt in (2,3):
            with pytest.raises((RuntimeError,InvalidUpdateError)):
                await graph.ainvoke(Command(update={key:attempt if key=='attempt_number' else initial[key]
                    for key in ('attempt_number','report_length','citation_style','max_sources','enforce_provider_budget')}),config=config)
        ready=True
        result,_=await worker._invoke_checkpointed_graph_unchecked(graph,{**initial,'attempt_number':4},task,run,None)
        assert attempts[-1]==4 and prepared==[True]
        assert result['claims']==[{'claim_id':'retained-evidence'}]


@pytest.mark.asyncio
async def test_approved_interrupt_is_not_repeated_after_downstream_failure():
    attempts,decisions=[],[]
    task=SimpleNamespace(id=uuid.uuid4(),resume_action='APPROVE_PLAN',resume_payload={'plan_version':1,'action':'APPROVE_PLAN'})
    run=SimpleNamespace(id=uuid.uuid4(),checkpoint_thread_id=str(uuid.uuid4()))
    async def wait(state):
        decision=interrupt({'kind':'PLAN_APPROVAL','plan_version':1})
        decisions.append(decision)
        return {'plan_approved':True}
    async def work(state):
        attempts.append(state['attempt_number'])
        if len(attempts)<2: raise RuntimeError('controlled downstream failure')
        return {'final_report_markdown':'# Approved draft'}
    builder=StateGraph(ResearchState)
    builder.add_node('approval',wait);builder.add_node('work',work)
    builder.add_edge(START,'approval');builder.add_edge('approval','work');builder.add_edge('work',END)
    graph=builder.compile(checkpointer=InMemorySaver())
    state={'task_id':str(task.id),'workflow_run_id':str(run.id),'attempt_number':1}
    await worker._invoke_checkpointed_graph_unchecked(graph,state,task,run,None)
    with pytest.raises(RuntimeError,match='controlled downstream failure'):
        await worker._invoke_checkpointed_graph_unchecked(graph,{**state,'attempt_number':2},task,run,None)
    task.resume_action=task.resume_payload=None
    result,_=await worker._invoke_checkpointed_graph_unchecked(graph,{**state,'attempt_number':3},task,run,None)
    assert attempts==[2,3] and len(decisions)==1 and result['plan_approved']
