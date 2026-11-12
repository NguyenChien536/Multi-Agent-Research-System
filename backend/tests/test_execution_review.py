import hashlib
from unittest.mock import AsyncMock
import pytest
from app.agents import nodes
from app.agents.graph import should_revise_draft
from app.services.evidence_review import prepare_evidence_review, evaluate_evidence_reviews, EvidenceReview
from app.services.manuscript import attach_manuscript_contract
from tests.manuscript_helpers import complete_manuscript, supported_critic_response
from tests.test_execution_evidence import valid_context


def test_executed_seed_fact_does_not_require_unrelated_literature(valid_context):
    text='## Experimental Setup\n\nThe seed of 42 is fixed for partitioning to ensure deterministic data allocation.'
    prepared=prepare_evidence_review(text,[],central_headings=[],draft=text,policy_version=4,execution_context=valid_context)
    assert prepared['substantive_findings']==[]
    fact=prepared['execution_facts'][0]
    assert fact['value']==42 and fact['analysis_run_id']==valid_context['analysis']['analysis_run_id']
    unit=prepared['units'][0]
    response=EvidenceReview(statement_id=unit['statement_id'],judgment='SUPPORTED',reason='Matches the executed partition.',
        supporting_execution_fact_ids=[fact['fact_id']])
    assert evaluate_evidence_reviews(prepared,[response])['all_supported']
    assert not evaluate_evidence_reviews(prepared,[response.model_copy(update={'supporting_execution_fact_ids':[]})])['all_supported']
    assert not evaluate_evidence_reviews(prepared,[response.model_copy(update={'supporting_execution_fact_ids':['invented-result']})])['all_supported']


def test_seed_fact_cannot_justify_scientific_guarantee_or_upgrade_history(valid_context):
    text='## Discussion\n\nSeed 42 ensures deterministic splitting and guarantees stable matching for all datasets.'
    for version in [3,4]:
        prepared=prepare_evidence_review(text,[],central_headings=[],draft=text,policy_version=version,execution_context=valid_context)
        assert prepared['substantive_findings']
        assert not prepared['execution_facts']
    procedure='## Methods\n\nSeed 42 ensures deterministic partitioning.'
    old=prepare_evidence_review(procedure,[],central_headings=[],draft=procedure,policy_version=3,execution_context=valid_context)
    assert old['substantive_findings'] and not old['execution_facts']


@pytest.mark.parametrize('requested,expected',[(0,'post_processor'),(1,'writer'),(2,'writer'),(3,'post_processor')])
def test_new_revision_slots_are_bounded_and_inclusive(requested,expected):
    plan=attach_manuscript_contract({},'REVIEW','en')
    assert should_revise_draft({'plan':plan,'critic_verdict':'REVISE','current_micro_revision':requested,'max_micro_revisions':2})==expected


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_verdict,expected',[('REVISE','REVISE'),('NEEDS_REVIEW','NEEDS_REVIEW')])
async def test_missing_source_allows_bounded_text_repair_without_scientific_pass(monkeypatch,provider_verdict,expected):
    from types import SimpleNamespace
    monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
    monkeypatch.setattr(nodes,'record_agent_run',AsyncMock())
    monkeypatch.setattr(nodes,'get_fast_llm',lambda:SimpleNamespace(with_structured_output=lambda _:object()))
    async def review(_state,_llm,messages,**kwargs):
        result=supported_critic_response(messages)
        result.verdict=provider_verdict
        result.feedback=['Narrow the unsupported comparison.']
        return result
    monkeypatch.setattr(nodes,'invoke_llm_with_budget',review)
    plan=attach_manuscript_contract({'evidence_needs':[{'need_id':'background','question':'What does the prior evidence support?'}]},'REVIEW','en')
    state={'plan':plan,'research_type':'REVIEW','language':'en','draft_report_markdown':complete_manuscript('This is a limited exploratory synthesis.',language='en'),
        'claims':[],'max_sources':1,'collected_sources':[{'url':'https://example.org/available'}],
        'evidence_need_coverage':{'needs':[{'need_id':'background','question':'Background support','role':'CORE_CONCEPT'}],'missing_need_ids':['background']}}
    result=await nodes.critic_node(state)
    assert result['critic_verdict']==expected
    delivered=await nodes.post_processor_node({**state,**result})
    assert delivered['status']=='NEEDS_REVIEW'
    exhausted=await nodes.critic_node({**state,'current_micro_revision':2})
    assert exhausted['critic_verdict']=='NEEDS_REVIEW'
    unchanged=await nodes.critic_node({**state,'current_micro_revision':1,'critic_review_metadata':{'draft_sha256':hashlib.sha256(state['draft_report_markdown'].encode()).hexdigest()}})
    assert unchanged['critic_verdict']=='NEEDS_REVIEW'

@pytest.mark.asyncio
async def test_real_graph_uses_both_allowed_revision_slots(monkeypatch):
    import uuid
    from app.agents import graph as graph_module
    from tests.test_graph_orchestration import _patch_external_boundaries
    _patch_external_boundaries(monkeypatch,critic_sequence=('REVISE','REVISE','PASS'))
    monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
    monkeypatch.setattr(nodes,'record_agent_run',AsyncMock())
    previous_supervisor=graph_module.supervisor_node
    async def current_policy_supervisor(state):
        result=await previous_supervisor(state)
        result['plan']=attach_manuscript_contract(result['plan'],'REVIEW','en')
        return result
    monkeypatch.setattr(graph_module,'supervisor_node',current_policy_supervisor)
    from types import SimpleNamespace
    async def critique(messages):
        response=supported_critic_response(messages)
        response.verdict='REVISE'
        return response
    critic=SimpleNamespace(ainvoke=AsyncMock(side_effect=critique))
    critic.with_structured_output=lambda _:critic
    monkeypatch.setattr(nodes,'get_fast_llm',lambda:critic)
    real_writer=graph_module.writer_node
    writes=[]
    async def tracked_writer(state):
        writes.append(1)
        result=await real_writer(state)
        result['draft_report_markdown'] += '\n\nControlled revision number '+str(len(writes))+'.'
        return result
    monkeypatch.setattr(graph_module,'writer_node',tracked_writer)
    graph=graph_module.build_research_graph()
    result=await graph.ainvoke({'task_id':str(uuid.uuid4()),'research_question':'A bounded controlled fixture question',
        'research_depth':'SHALLOW','language':'en','current_iteration':0,'current_micro_revision':0,
        'max_iterations':1,'max_micro_revisions':2,'collected_sources':[],'visited_urls':set(),'claims':[]})
    assert len(writes)==3, 'One initial draft plus exactly two permitted repairs'
    assert result['current_micro_revision']==2
    assert result['critic_verdict']=='NEEDS_REVIEW'
    assert result['status']=='NEEDS_REVIEW'
