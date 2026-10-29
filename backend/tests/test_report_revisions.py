"""Version/ownership/lifecycle checks; provider boundaries are deterministic."""
import asyncio
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.grounding import Citation
from app.models.report import ResearchReport, ReportVersion
from app.models.report_revision import ReportRevision
from app.models.source import ResearchSource, DocumentChunk
from app.models.task import ResearchTask, TaskDispatchOutbox, WorkflowRun
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.services.grounding import persist_grounded_claims
from app.services.manuscript import manuscript_contract
from app.services import task_dispatcher
from app.agents import nodes, graph as graph_module
from app import worker
from tests.manuscript_helpers import complete_manuscript
from tests.test_report_versions import _register_and_login


@pytest_asyncio.fixture
async def paper():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        suffix=uuid.uuid4().hex[:10]
        owner=await _register_and_login(client,f"revision_owner_{suffix}")
        other=await _register_and_login(client,f"revision_reader_{suffix}")
        result=await client.post('/api/v1/research',headers=owner,json={
            'title':'Editorial revision test','research_question':'How can a revision preserve its original evidence?', 'language':'en'})
        tid=uuid.UUID(result.json()['id'])
        async with AsyncSessionLocal() as db:
            task=await db.get(ResearchTask,tid); task.status='COMPLETED'
            task.completed_at=datetime.now(timezone.utc)
            source=ResearchSource(research_task_id=tid,source_tag='src_01',title='Verified original study',url='https://example.org/original')
            db.add(source); await db.flush()
            chunk=DocumentChunk(research_task_id=tid,source_id=source.id,chunk_index=0,content='The recorded result is grounded in this original passage.')
            db.add(chunk); await db.flush()
            claims=await persist_grounded_claims(db,tid,[{'claim':'The result has source evidence.','evidence_quote':'The recorded result is grounded in this original passage.'}],[chunk])
            report=ResearchReport(research_task_id=tid); db.add(report); await db.flush()
            base=ReportVersion(report_id=report.id,version_number=1,title='Original article',content_markdown=complete_manuscript('An original finding [1].',language='en'),
                review_status='PASSED',review_metadata={'manuscript_contract':manuscript_contract('REVIEW','en'),
                    'method_provenance':{'available_source_count':1,'search_activity_this_run':[]}},word_count=300)
            db.add(base); await db.flush()
            db.add(Citation(research_task_id=tid,report_id=report.id,report_version_id=base.id,
                claim_id=uuid.UUID(claims[0]['claim_id']),source_id=source.id,chunk_id=chunk.id,citation_label='[1]',citation_number=1))
            await db.commit()
            snapshot=(base.title,base.content_markdown,deepcopy(base.review_metadata))
            base_id=base.id; uid=task.user_id
        yield SimpleNamespace(client=client,owner=owner,other=other,tid=tid,uid=uid,base_id=base_id,claims=claims,snapshot=snapshot,
            url=f'/api/v1/research/{tid}/report/versions/1/revisions')
        # Never leave an unclaimed event to affect unrelated dispatcher tests.
        async with AsyncSessionLocal() as db:
            await db.execute(update(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id==tid).values(dispatched_at=datetime.now(timezone.utc)))
            await db.execute(update(ResearchTask).where(ResearchTask.id==tid).values(status='CANCELLED',worker_lease_until=None))
            await db.execute(update(ReportRevision).where(ReportRevision.research_task_id==tid,ReportRevision.status.in_(['QUEUED','RUNNING'])).values(status='CANCELLED'))
            await db.commit()


def payload(**changes):
    return {'request_id':str(uuid.uuid4()),'instructions':'Clarify the Introduction and discuss the limits of the available evidence.',**changes}


@pytest.mark.asyncio
async def test_revision_admission_owner_idempotency_and_cancel_history(paper):
    p=paper
    assert (await p.client.post(p.url,json=payload())).status_code==401
    assert (await p.client.post(p.url,headers=p.other,json=payload())).status_code==404
    assert (await p.client.get(p.url,headers=p.other)).status_code==404
    request=payload()
    first=await p.client.post(p.url,headers=p.owner,json=request)
    assert first.status_code==202,first.text
    assert first.json()['status']=='QUEUED'
    assert 'no-store' in first.headers['cache-control']
    same=await p.client.post(p.url,headers=p.owner,json=request)
    assert same.json()['id']==first.json()['id']
    assert (await p.client.post(p.url,headers=p.owner,json={**request,'instructions':'A different editorial request with the same ID.'})).status_code==409
    assert (await p.client.post(p.url,headers=p.owner,json=payload())).status_code==409
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(ReportRevision.id)).where(ReportRevision.research_task_id==p.tid))==1
        event=await db.scalar(select(TaskDispatchOutbox).where(TaskDispatchOutbox.research_task_id==p.tid))
        assert event.dispatched_at is None
    await p.client.post(f'/api/v1/research/{p.tid}/cancel',headers=p.owner)
    history=await p.client.get(p.url,headers=p.owner)
    assert history.json()[0]['status']=='CANCELLED'


@pytest.mark.asyncio
async def test_revision_rejects_stale_version_invalid_snapshot_and_body(paper):
    p=paper
    assert (await p.client.post(p.url,headers=p.owner,json=payload(instructions=' '))).status_code==422
    assert (await p.client.post(p.url,headers=p.owner,json=payload(budget={'max_cost_usd':999}))).status_code==422
    async with AsyncSessionLocal() as db:
        base=await db.get(ReportVersion,p.base_id)
        base.review_metadata={**base.review_metadata,'manuscript_contract':manuscript_contract('EMPIRICAL_HUMAN','en')}
        await db.commit()
    response=await p.client.post(p.url,headers=p.owner,json=payload())
    assert response.status_code==409 and 'frozen fieldwork' in response.text
    async with AsyncSessionLocal() as db:
        base=await db.get(ReportVersion,p.base_id); base.review_metadata=p.snapshot[2]
        db.add(ReportVersion(report_id=base.report_id,version_number=2,title='A newer draft',content_markdown='# Newer'))
        await db.commit()
    assert (await p.client.post(p.url,headers=p.owner,json=payload())).status_code==409


@pytest.mark.asyncio
async def test_competing_revision_requests_admit_exactly_one(paper):
    results=await asyncio.gather(*(paper.client.post(paper.url,headers=paper.owner,json=payload()) for _ in range(2)))
    assert sorted(r.status_code for r in results)==[202,409]


def install_editorial_providers(monkeypatch, paper, *, cancel=False, research_type='REVIEW', delete=False):
    writer=object(); critic=SimpleNamespace(with_structured_output=lambda _: 'critic')
    monkeypatch.setattr(nodes,'get_smart_llm',lambda:writer)
    monkeypatch.setattr(nodes,'get_fast_llm',lambda:critic)
    monkeypatch.setattr(nodes,'get_active_model_name',lambda **_: 'test-provider')
    async def forbidden(_):
        raise AssertionError('Editorial revision must not search, ingest, analyze new evidence or execute experiments')
    for name in ('supervisor_node','researcher_node','curator_node','analyst_node','methodologist_node','experiment_runner_node'):
        monkeypatch.setattr(graph_module,name,forbidden)
    async def invoke(state,llm,messages,**kwargs):
        if llm=='critic':
            return nodes.CriticVerdict(verdict='PASS',feedback=[],missing_areas=[])
        prompt=messages[0].content
        assert 'EDITORIAL REVISION' in prompt and 'Original article' not in prompt  # Base body, not a fabricated title/summary.
        assert 'An original finding' in prompt and 'Clarify the Introduction' in prompt
        if cancel:
            result=await paper.client.post(f'/api/v1/research/{paper.tid}/cancel',headers=paper.owner)
            assert result.status_code==200
        if delete:
            result=await paper.client.delete(f'/api/v1/research/{paper.tid}',headers=paper.owner)
            assert result.status_code==202
        marker=f"[[@claim:{paper.claims[0]['claim_id']}]]"
        return SimpleNamespace(content=complete_manuscript(f'Revised interpretation retains original source {marker}.',research_type=research_type,language='en',prompt=prompt))
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',invoke)
    monkeypatch.setattr(task_dispatcher,'execute_research_workflow',SimpleNamespace(delay=lambda _:None))


@pytest.mark.asyncio
async def test_worker_publishes_a_new_version_without_research_and_keeps_base(paper,monkeypatch):
    p=paper; install_editorial_providers(monkeypatch,p)
    response=await p.client.post(p.url,headers=p.owner,json=payload()); assert response.status_code==202,response.text
    result=await worker.run_langgraph_workflow(str(p.tid))
    assert result['status']=='SUCCESS'
    versions=(await p.client.get(f'/api/v1/research/{p.tid}/report/versions',headers=p.owner)).json()
    assert [v['version_number'] for v in versions]==[2,1]
    async with AsyncSessionLocal() as db:
        base=await db.get(ReportVersion,p.base_id)
        assert (base.title,base.content_markdown,base.review_metadata)==p.snapshot
        new=await db.scalar(select(ReportVersion).where(ReportVersion.report_id==base.report_id,ReportVersion.version_number==2))
        assert new.review_status=='PASSED',new.review_metadata
        assert new.review_metadata['revision']['base_version_id']==str(base.id)
        assert new.review_metadata['method_provenance']==p.snapshot[2]['method_provenance']
        request=await db.get(ReportRevision,uuid.UUID(response.json()['id']))
        assert request.status=='COMPLETED' and request.result_version_id==new.id
        assert await db.scalar(select(func.count(Citation.id)).where(Citation.report_version_id==new.id))==1
    duplicate=await worker.run_langgraph_workflow(str(p.tid))
    assert duplicate['status']!='SUCCESS'


@pytest.mark.asyncio
async def test_cancel_during_revision_never_publishes_late_output(paper,monkeypatch):
    p=paper; install_editorial_providers(monkeypatch,p,cancel=True)
    await p.client.post(p.url,headers=p.owner,json=payload())
    await worker.run_langgraph_workflow(str(p.tid))
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(ReportVersion.id)).join(ResearchReport).where(ResearchReport.research_task_id==p.tid))==1
    history=await p.client.get(p.url,headers=p.owner)
    assert history.json()[0]['status']=='CANCELLED'


@pytest.mark.asyncio
async def test_identical_concurrent_retries_have_one_request_identity(paper):
    request=payload()
    results=await asyncio.gather(*(paper.client.post(paper.url,headers=paper.owner,json=request) for _ in range(2)))
    assert all(r.status_code==202 for r in results)
    assert len({r.json()['id'] for r in results})==1


@pytest.mark.asyncio
async def test_budget_failure_preserves_base_and_reports_request_failure(paper,monkeypatch):
    from app.services.provider_budget import ProviderBudgetExceeded
    install_editorial_providers(monkeypatch,paper)
    async def exhausted(*args,**kwargs):
        raise ProviderBudgetExceeded('Output token budget exhausted')
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',exhausted)
    await paper.client.post(paper.url,headers=paper.owner,json=payload())
    with pytest.raises(RuntimeError):
        await worker.run_langgraph_workflow(str(paper.tid))
    result=(await paper.client.get(paper.url,headers=paper.owner)).json()[0]
    assert result['status']=='FAILED' and result['error_code']=='BUDGET_LIMIT'
    async with AsyncSessionLocal() as db:
        base=await db.get(ReportVersion,paper.base_id)
        assert base.content_markdown==paper.snapshot[1]
        assert await db.scalar(select(func.count(ReportVersion.id)).where(ReportVersion.report_id==base.report_id))==1


@pytest.mark.asyncio
async def test_deleting_during_revision_never_recreates_output(paper,monkeypatch):
    install_editorial_providers(monkeypatch,paper,delete=True)
    await paper.client.post(paper.url,headers=paper.owner,json=payload())
    await worker.run_langgraph_workflow(str(paper.tid))
    assert (await paper.client.get(paper.url,headers=paper.owner)).status_code==404
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(ReportVersion.id)).join(ResearchReport).where(ResearchReport.research_task_id==paper.tid))==1


@pytest.mark.asyncio
async def test_revision_ignores_unversioned_sources_and_rejects_broken_lineage(paper):
    from app.services.report_revisions import revision_inputs
    async with AsyncSessionLocal() as db:
        task=await db.get(ResearchTask,paper.tid); base=await db.get(ReportVersion,paper.base_id)
        new_source=ResearchSource(research_task_id=paper.tid,source_tag='src_99',title='New source outside the base version',url='https://example.org/new')
        db.add(new_source); await db.flush()
        new_chunk=DocumentChunk(research_task_id=paper.tid,source_id=new_source.id,chunk_index=0,content='A different later result.')
        db.add(new_chunk); await db.flush()
        context=await revision_inputs(db,task,base)
        assert [c['claim_id'] for c in context['claims']]==[paper.claims[0]['claim_id']]
        assert str(new_source.id) not in str(context)
        citation=await db.scalar(select(Citation).where(Citation.report_version_id==base.id))
        citation.chunk_id=new_chunk.id
        await db.commit()
    response=await paper.client.post(paper.url,headers=paper.owner,json=payload())
    assert response.status_code==409 and 'evidence' in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize('research_type',['EMPIRICAL_COMPUTATIONAL','EMPIRICAL_HUMAN'])
async def test_empirical_revision_uses_frozen_inputs_and_does_not_repeat_analysis(paper,monkeypatch,research_type):
    p=paper
    analysis={'status':'COMPLETED','routine_name':'tabular_regression_v1','metrics':{'baseline':{'mae':3.0},'model':{'mae':1.5}},'manifest':{'test_rows':12},'reproducibility_status':'PASSED'}
    human={'sample_size':12,'method_notes':'Frozen fieldwork method.','results_summary':'The original recorded observation.', 'data_provenance':'Original researcher-supplied data.'}
    async with AsyncSessionLocal() as db:
        task=await db.get(ResearchTask,p.tid); base=await db.get(ReportVersion,p.base_id)
        task.research_type=research_type
        task.user_data_submission={'sample_size':999999,'results_summary':'NEW UNRELATED DATA MUST NOT BE USED'}
        meta=deepcopy(base.review_metadata); meta['manuscript_contract']=manuscript_contract(research_type,'en')
        meta['manuscript_input_snapshot']={'research_type':research_type,'analysis_run':analysis if research_type=='EMPIRICAL_COMPUTATIONAL' else None,
            'user_data_submission':human if research_type=='EMPIRICAL_HUMAN' else None,'protocol':{'study_design':'Frozen original design'}}
        base.review_metadata=meta
        base.content_markdown=complete_manuscript('An original finding [1].',research_type=research_type,language='en')
        await db.commit()
    install_editorial_providers(monkeypatch,p,research_type=research_type)
    original_invoke=nodes.invoke_llm_with_budget
    async def verify_snapshot(state,llm,messages,**kwargs):
        assert 'NEW UNRELATED' not in messages[0].content
        assert state['analysis_run']==(analysis if research_type=='EMPIRICAL_COMPUTATIONAL' else None)
        assert state['user_data_submission']==(human if research_type=='EMPIRICAL_HUMAN' else None)
        return await original_invoke(state,llm,messages,**kwargs)
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',verify_snapshot)
    response=await p.client.post(p.url,headers=p.owner,json=payload()); assert response.status_code==202,response.text
    result=await worker.run_langgraph_workflow(str(p.tid)); assert result['status']=='SUCCESS'
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(AnalysisRun.id)).where(AnalysisRun.research_task_id==p.tid))==0
        assert await db.scalar(select(func.count(ExperimentJournalEntry.id)).where(ExperimentJournalEntry.research_task_id==p.tid))==0
        request=await db.get(ReportRevision,uuid.UUID(response.json()['id']))
        assert request.status=='COMPLETED'


@pytest.mark.asyncio
async def test_missing_evidence_stops_revision_without_starting_a_research_loop(paper,monkeypatch):
    install_editorial_providers(monkeypatch,paper)
    original=nodes.invoke_llm_with_budget
    async def missing(state,llm,messages,**kwargs):
        if llm=='critic':
            return nodes.CriticVerdict(verdict='NEED_MORE_DATA',feedback=['This requires an additional study.'],missing_areas=['An external experiment'])
        return await original(state,llm,messages,**kwargs)
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',missing)
    response=await paper.client.post(paper.url,headers=paper.owner,json=payload())
    assert (await worker.run_langgraph_workflow(str(paper.tid)))['status']=='SUCCESS'
    history=(await paper.client.get(paper.url,headers=paper.owner)).json()
    assert history[0]['id']==response.json()['id'] and history[0]['status']=='NEEDS_REVIEW'


@pytest.mark.asyncio
async def test_a_late_revision_cannot_publish_over_a_newer_version(paper,monkeypatch):
    install_editorial_providers(monkeypatch,paper)
    original=nodes.invoke_llm_with_budget
    inserted=False
    async def competing(state,llm,messages,**kwargs):
        nonlocal inserted
        if llm!='critic' and not inserted:
            inserted=True
            async with AsyncSessionLocal() as db:
                base=await db.get(ReportVersion,paper.base_id)
                db.add(ReportVersion(report_id=base.report_id,version_number=2,title='Competing update',content_markdown='# Competing version'))
                await db.commit()
        return await original(state,llm,messages,**kwargs)
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',competing)
    await paper.client.post(paper.url,headers=paper.owner,json=payload())
    with pytest.raises(RuntimeError):
        await worker.run_langgraph_workflow(str(paper.tid))
    versions=(await paper.client.get(f'/api/v1/research/{paper.tid}/report/versions',headers=paper.owner)).json()
    assert len(versions)==2 and versions[0]['content_markdown']=='# Competing version'


@pytest.mark.asyncio
async def test_worker_crash_after_checkpoint_redelivers_without_repeating_provider_calls(paper,monkeypatch):
    class WorkerCrash(BaseException):
        pass
    install_editorial_providers(monkeypatch,paper)
    original_invoke=nodes.invoke_llm_with_budget
    calls=0
    async def count_calls(*args,**kwargs):
        nonlocal calls
        calls+=1
        return await original_invoke(*args,**kwargs)
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',count_calls)
    original_graph=worker._invoke_checkpointed_graph
    async def crash_after_checkpoint(*args,**kwargs):
        await original_graph(*args,**kwargs)
        raise WorkerCrash()
    monkeypatch.setattr(worker,'_invoke_checkpointed_graph',crash_after_checkpoint)
    response=await paper.client.post(paper.url,headers=paper.owner,json=payload())
    with pytest.raises(WorkerCrash):
        await worker.run_langgraph_workflow(str(paper.tid))
    first_calls=calls
    assert first_calls>0
    async with AsyncSessionLocal() as db:
        task=await db.get(ResearchTask,paper.tid)
        assert task.status=='RUNNING'
        task.worker_lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
        await db.commit()
    await task_dispatcher.recover_expired_worker_claims()
    monkeypatch.setattr(worker,'_invoke_checkpointed_graph',original_graph)
    assert (await worker.run_langgraph_workflow(str(paper.tid)))['status']=='SUCCESS'
    assert calls==first_calls
    async with AsyncSessionLocal() as db:
        request=await db.get(ReportRevision,uuid.UUID(response.json()['id']))
        assert request.status=='COMPLETED'
        result=await db.get(ReportVersion,request.result_version_id)
        assert result.workflow_run_id==request.workflow_run_id
        assert await db.scalar(select(func.count(ReportVersion.id)).where(ReportVersion.workflow_run_id==request.workflow_run_id))==1


@pytest.mark.asyncio
async def test_publication_python_error_rolls_back_flushed_version_and_citations(paper,monkeypatch):
    install_editorial_providers(monkeypatch,paper)
    response=await paper.client.post(paper.url,headers=paper.owner,json=payload())
    fired=False
    def fail_once(session,context,instances):
        nonlocal fired
        if not fired and any(isinstance(item,Citation) and item.research_task_id==paper.tid for item in session.new):
            fired=True
            raise RuntimeError('Simulated publication failure after version flush')
    event.listen(Session,'before_flush',fail_once)
    try:
        with pytest.raises(RuntimeError):
            await worker.run_langgraph_workflow(str(paper.tid))
    finally:
        event.remove(Session,'before_flush',fail_once)
    assert fired
    async with AsyncSessionLocal() as db:
        request=await db.get(ReportRevision,uuid.UUID(response.json()['id']))
        assert request.status=='FAILED' and request.result_version_id is None
        assert await db.scalar(select(func.count(ReportVersion.id)).join(ResearchReport).where(ResearchReport.research_task_id==paper.tid))==1
