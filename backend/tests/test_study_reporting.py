from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.agents import nodes
from app.services.manuscript import manuscript_contract
from app.services.scientific_paper import scientific_context, validate_scientific_reporting
from app.services.study_protocol import render_protocol


def findings(text, provenance='', kind='EMPIRICAL_HUMAN', section='Methods'):
    context=scientific_context({'user_data_submission':{'method_notes':provenance}})
    return {item['code'] for item in validate_scientific_reporting('## '+section+'\n'+text,manuscript_contract(kind,'en'),context,[])}


@pytest.mark.parametrize('text',[
    'These items were adapted from validated cognitive trust scales.',
    'No real participants were recruited; these items were adapted from validated scales.',
    'We derived our questionnaire from the published instrument.',
])
def test_cited_or_proposed_instruments_do_not_attest_current_study_adaptation(text):
    assert 'UNRECORDED_INSTRUMENT_ADAPTATION' in findings(text)


@pytest.mark.parametrize('text',[
    'These synthetic items were not adapted from a validated questionnaire.',
    'Future researchers could adapt the questionnaire from validated scales.',
    'Previous studies adapted items from validated scales.',
])
def test_negative_future_and_prior_method_descriptions_are_not_current_actions(text):
    assert 'UNRECORDED_INSTRUMENT_ADAPTATION' not in findings(text)


def test_only_explicit_user_record_can_supply_method_provenance_not_a_proposed_protocol():
    text='These items were adapted from validated scales.'
    assert 'UNRECORDED_INSTRUMENT_ADAPTATION' not in findings(text, 'We adapted the questionnaire from a validated scale; source and translation process recorded by the researcher.')
    assert 'UNRECORDED_INSTRUMENT_ADAPTATION' in findings(text, 'Synthetic demonstration only. No validated questionnaire or real participants.')
    assert 'UNRECORDED_INSTRUMENT_VALIDATION' in findings('We validated the questionnaire using a pilot sample.')
    assert 'UNRECORDED_INSTRUMENT_VALIDATION' not in findings('We validated the questionnaire using a pilot sample.', 'We validated the questionnaire using the uploaded pilot data.')


@pytest.mark.parametrize('text,flag',[
    ('The literature lacks validated scales for these assistants.',True),
    ('No prior studies compared these methods.',True),
    ('No prior studies in the retrieved corpus compared these methods.',False),
    ('We cannot claim this is the first study.',False),
    ('This is not the first study of these methods.',False),
])
def test_research_gap_is_bounded_to_observed_corpus(text,flag):
    assert ('UNBOUNDED_RESEARCH_GAP' in findings(text,kind='REVIEW',section='Introduction')) == flag


def test_new_reporting_policy_does_not_reassess_historical_contracts():
    contract=manuscript_contract('EMPIRICAL_HUMAN','en');contract.pop('study_provenance_policy');contract['version']=5
    rows=validate_scientific_reporting('## Methods\nThese items were adapted from validated scales.',contract,{},[])
    assert not any(r['code'].startswith('UNRECORDED_') for r in rows)


def test_unresolved_internal_citations_are_flagged_only_under_the_new_rendering_policy():
    contract=manuscript_contract('EMPIRICAL_COMPUTATIONAL','en')
    text='## Results\nRecorded result [[metrics:model]] is not an actual citation.'
    assert 'UNRESOLVED_INTERNAL_MARKER' in {r['code'] for r in validate_scientific_reporting(text,contract,{},[])}
    contract.pop('rendering_policy')
    assert 'UNRESOLVED_INTERNAL_MARKER' not in {r['code'] for r in validate_scientific_reporting(text,contract,{},[])}


@pytest.mark.parametrize('language',['en','vi','fr','de','es','ja','zh','ko'])
def test_rendered_protocol_has_exact_fields_and_never_fabricates_hypotheses(language):
    plan=dict(research_questions=['Recorded RQ'],hypotheses=[],variables={'control':['Recorded variable']},
              study_design='Descriptive only.',data_collection_procedure='Await uploaded CSV.',
              analysis_plan='Descriptive statistics only.',ethical_considerations='No human collection in synthetic demo.')
    markdown=render_protocol(plan,language)
    assert markdown.count('\n\n## ')==7
    assert all(value in markdown for value in ('Recorded RQ','Recorded variable','Descriptive only.','Await uploaded CSV.'))
    assert 'H1' not in markdown and '120' not in markdown
    assert 'protocol_markdown' not in nodes.MethodologistPlan.model_json_schema()['properties']


@pytest.mark.asyncio
async def test_methodologist_generates_fields_once_and_renders_the_same_proposed_plan(monkeypatch):
    plan=nodes.MethodologistPlan(research_questions=['A descriptive question?'],hypotheses=[],variables={'outcomes':['usefulness']},study_design='Synthetic example.',
      data_collection_procedure='Await researcher data.',analysis_plan='Descriptive arithmetic.',ethical_considerations='No actual participants.')
    calls=[]
    class LLM:
        def with_structured_output(self,schema):
            assert schema is nodes.MethodologistPlan
            return self
        async def ainvoke(self,messages):calls.append(messages);return plan
    monkeypatch.setattr(nodes,'get_smart_llm',lambda:LLM())
    monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
    monkeypatch.setattr(nodes,'record_agent_run',AsyncMock())
    result=await nodes.methodologist_node({'research_type':'EMPIRICAL_HUMAN','language':'en','research_question':'Question?'})
    assert len(calls)==1 and result['status']=='WAITING_USER_DATA'
    assert result['protocol']['hypotheses']==[]
    assert result['protocol']['protocol_markdown']==render_protocol(plan.model_dump(),'en')
