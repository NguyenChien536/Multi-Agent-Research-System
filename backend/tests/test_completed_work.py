import json,re,uuid
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from langchain_core.messages import AIMessage,HumanMessage
from pydantic import BaseModel
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask,WorkflowRun
from app.models.provider_result import ProviderResult
from app.agents import nodes
from app.services.completed_work import CompletedWork
from app.services.provider_budget import ResearchTaskStopped
from app.services.sectional_writer import write_section_groups,section_groups,ManuscriptSectionIncomplete
from app.services.sectional_writer import group_schema, group_message
from app.services.manuscript import manuscript_contract
from app.services.public_errors import ProviderResponseTimeout
from tests.test_provider_budget import create_running_task,delete_test_user

@pytest.mark.asyncio
async def test_completed_json_is_reused_only_for_the_same_run_inputs_and_current_claim():
 tid,uid=await create_running_task();rid=uuid.uuid4();calls=[]
 class Output(BaseModel):answer:str
 class Model:
  async def ainvoke(self,messages):calls.append(True);return Output(answer='verified input')
 chain=nodes.BudgetedFallbackLLM([('gpt-4o-mini',Model())],structured_schema=Output)
 state={'task_id':str(tid),'workflow_run_id':str(rid),'attempt_number':1,'enforce_provider_budget':True}
 try:
  async with AsyncSessionLocal() as db:
   db.add(WorkflowRun(id=rid,research_task_id=tid,run_number=1,status='RUNNING',checkpoint_thread_id=str(uuid.uuid4())));await db.commit()
  await nodes.invoke_llm_with_budget(state,chain,[HumanMessage(content='passage A')],model_name='gpt-4o-mini')
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);t.attempt_number=2;await db.commit()
  response=await nodes.invoke_llm_with_budget({**state,'attempt_number':2},chain,[HumanMessage(content='passage A')],model_name='gpt-4o-mini')
  assert len(calls)==1 and nodes.extract_tokens(response,'prompt','answer')==(0,0)
  await nodes.invoke_llm_with_budget({**state,'attempt_number':2},chain,[HumanMessage(content='different passage')],model_name='gpt-4o-mini')
  assert len(calls)==2
  async with AsyncSessionLocal() as db:
   t=await db.get(ResearchTask,tid);assert t.budget_config['_provider_usage']['llm_calls']==2
   t.status='CANCELLED';await db.commit()
  with pytest.raises(ResearchTaskStopped):
   await nodes.invoke_llm_with_budget({**state,'attempt_number':2},chain,[HumanMessage(content='passage A')],model_name='gpt-4o-mini')
  assert len(calls)==2
 finally:await delete_test_user(uid)

@pytest.mark.asyncio
async def test_foreign_run_cannot_read_or_save_private_completed_work():
 tid,uid=await create_running_task();other,other_uid=await create_running_task();rid=uuid.uuid4()
 try:
  async with AsyncSessionLocal() as db:
   db.add(WorkflowRun(id=rid,research_task_id=tid,run_number=1,status='RUNNING',checkpoint_thread_id=str(uuid.uuid4())));await db.commit()
  store=CompletedWork.for_state({'task_id':str(other),'workflow_run_id':str(rid),'attempt_number':1,'enforce_provider_budget':True})
  with pytest.raises(ResearchTaskStopped):await store.load('json:fixture','a'*64)
  with pytest.raises(ResearchTaskStopped):await store.save('json:fixture','a'*64,{'private':'never save'})
  async with AsyncSessionLocal() as db:assert await db.scalar(select(func.count(ProviderResult.id)).where(ProviderResult.research_task_id==other))==0
 finally:
  await delete_test_user(uid);await delete_test_user(other_uid)

class MemoryStore:
 def __init__(self):self.rows={};self.progress=[]
 def fingerprint(self,value):return json.dumps(value,sort_keys=True,ensure_ascii=False)
 async def load(self,operation,digest):return self.rows.get((operation,digest))
 async def save(self,operation,digest,payload):self.rows[(operation,digest)]=payload
 async def writing_progress(self,done,total):self.progress.append((done,total))

def chunk_response(messages):
 headings=json.loads(re.search(r'order and spelling: (.+)\.',messages[0].content.splitlines()[0])[1])
 return AIMessage(content='\n\n'.join('## '+name+'\n### Evidence and scope\nThe supplied evidence supports this bounded interpretation; no unrecorded result is asserted.' for name in headings),usage_metadata={'input_tokens':50,'output_tokens':30,'total_tokens':80},response_metadata={'finish_reason':'STOP'})

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['REVIEW','EMPIRICAL_COMPUTATIONAL','EMPIRICAL_HUMAN'])
@pytest.mark.parametrize('language',['en','vi'])
@pytest.mark.parametrize('length',['SHORT','MEDIUM','LONG'])
async def test_every_article_type_and_length_assembles_only_complete_saved_groups(kind,language,length):
 store=MemoryStore();calls=[];contract=manuscript_contract(kind,language)
 async def invoke(messages):calls.append(messages);return chunk_response(messages)
 response=await write_section_groups({'research_question':'Question','report_length':length},'grounded brief',contract,store,invoke)
 assert re.findall(r'^## (.+)',response.content,re.M)==[section['heading'] for section in contract['sections']]
 assert store.progress[-1]==(len(section_groups(contract)),len(section_groups(contract)))
 count=len(calls)
 cached=await write_section_groups({'research_question':'Question','report_length':length},'grounded brief',contract,store,invoke)
 assert len(calls)==count and nodes.extract_tokens(cached,'prompt','answer')==(0,0)
 assert 'previously saved' in calls[-1][0].content.lower()

@pytest.mark.asyncio
async def test_interrupted_writing_keeps_completed_groups_without_delivering_a_partial_paper():
 store=MemoryStore();calls=[];contract=manuscript_contract('REVIEW','en')
 async def invoke(messages):
  calls.append(messages)
  if len(calls)==2:raise ProviderResponseTimeout('PROVIDER_TIMEOUT')
  return chunk_response(messages)
 with pytest.raises(ProviderResponseTimeout):await write_section_groups({'research_question':'Question'},'brief',contract,store,invoke)
 assert len(store.rows)==1 and store.progress==[(1,len(section_groups(contract)))]
 result=await write_section_groups({'research_question':'Question'},'brief',contract,store,invoke)
 assert result.response_metadata['reused_groups']==1
 assert len(calls)==len(section_groups(contract))+1

@pytest.mark.asyncio
@pytest.mark.parametrize('truncated',[False,True])
async def test_wrong_headings_or_truncated_groups_are_never_saved(truncated):
 store=MemoryStore()
 async def invoke(messages):
  response=chunk_response(messages)
  if truncated:response.response_metadata['finish_reason']='LENGTH'
  else:response.content+='\n## Unrequested findings\nInvented result'
  return response
 with pytest.raises(ManuscriptSectionIncomplete):await write_section_groups({},'brief',manuscript_contract('REVIEW','en'),store,invoke)
 assert not store.rows

@pytest.mark.asyncio
async def test_writer_node_persists_sectional_strategy_and_resumes_after_another_timeout(monkeypatch):
 from app.services.manuscript import attach_manuscript_contract
 store=MemoryStore();calls=[];monolithic=[]
 monkeypatch.setattr(CompletedWork,'for_state',lambda state:store)
 monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
 record=AsyncMock();monkeypatch.setattr(nodes,'record_agent_run',record)
 monkeypatch.setattr(nodes,'get_smart_llm',lambda:object())
 monkeypatch.setattr(nodes,'get_active_model_name',lambda **kwargs:'fixture')
 async def invoke(state,llm,messages,**kwargs):
  calls.append(messages)
  if len(messages)==1:
   monolithic.append(True);raise ProviderResponseTimeout('PROVIDER_TIMEOUT')
  if len(calls)==3:raise ProviderResponseTimeout('PROVIDER_TIMEOUT')
  return chunk_response(messages)
 monkeypatch.setattr(nodes,'invoke_llm_with_budget',invoke)
 state={'plan':attach_manuscript_contract({},'REVIEW','en'),'research_question':'Fixture question','research_type':'REVIEW','language':'en'}
 with pytest.raises(ProviderResponseTimeout):await nodes.writer_node(state)
 result=await nodes.writer_node(state)
 assert len(monolithic)==1
 assert '## Conclusion' in result['draft_report_markdown'] and not result['draft_truncated']
 assert record.await_args.kwargs['output_summary']['writer_strategy']=='sectional_resume_v1'
 assert record.await_args.kwargs['output_summary']['reused_groups']==1

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['REVIEW','EMPIRICAL_COMPUTATIONAL','EMPIRICAL_HUMAN'])
async def test_personal_long_papers_start_with_saved_sections_without_a_wasted_full_attempt(monkeypatch,kind):
 from types import SimpleNamespace
 from app.services import model_connection
 from app.services.manuscript import attach_manuscript_contract
 store=MemoryStore();calls=[]
 monkeypatch.setattr(CompletedWork,'for_state',lambda state:store)
 monkeypatch.setattr(model_connection,'current_connection',lambda:SimpleNamespace(output_token_limit=8192,model_tag='fixture',estimate=lambda *_:0))
 monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
 monkeypatch.setattr(nodes,'record_agent_run',AsyncMock())
 monkeypatch.setattr(nodes,'get_smart_llm',lambda:object())
 monkeypatch.setattr(nodes,'get_active_model_name',lambda **kwargs:'fixture')
 async def invoke(state,llm,messages,**kwargs):
  assert len(messages)>1, 'The full-paper attempt must not precede incremental writing'
  calls.append(messages)
  return chunk_response(messages)
 monkeypatch.setattr(nodes,'invoke_llm_with_budget',invoke)
 state={'plan':attach_manuscript_contract({},kind,'en'),'research_question':'Fixture question','research_type':kind,'language':'en','report_length':'MEDIUM'}
 result=await nodes.writer_node(state)
 count=len(section_groups(state['plan']['manuscript_contract']))
 assert len(calls)==count and store.progress[-1]==(count,count)
 assert '## Conclusion' in result['draft_report_markdown'] and not result['draft_truncated']
 await nodes.writer_node(state)
 assert len(calls)==count


def test_typed_group_assembles_requested_headings_in_order_without_inventing_content():
 schema=group_schema(['Introduction','Methods'])
 response=schema(title='Measured study',sections=[
  {'heading':'Methods','body':'### Recorded method\nOnly recorded inputs and executed actions are described.'},
  {'heading':'Introduction','body':'### Background\nThe supplied sources support this bounded research question.'}])
 message=group_message(response,['Introduction','Methods'])
 assert message.content.index('## Introduction') < message.content.index('## Methods')
 assert 'Only recorded inputs' in message.content
 object.__setattr__(response,'_reused_provider_result',True)
 assert nodes.extract_tokens(group_message(response,['Introduction','Methods']),'prompt','text')==(0,0)


@pytest.mark.parametrize('failure',['missing','unknown','duplicate','extra_heading'])
def test_typed_group_refuses_missing_unknown_duplicate_or_extra_sections(failure):
 from pydantic import ValidationError
 schema=group_schema(['Introduction','Methods'])
 sections=[{'heading':h,'body':'A substantive section with recorded and bounded evidence.'} for h in ['Introduction','Methods']]
 if failure=='missing':sections.pop()
 if failure=='unknown':sections[1]['heading']='Invented results'
 if failure=='duplicate':sections[1]['heading']='Introduction'
 if failure=='extra_heading':sections[1]['body']+='\n## Unexpected results\nUnrecorded results do not belong here.'
 with pytest.raises((ValidationError,ManuscriptSectionIncomplete)):
  group_message(schema(title='',sections=sections),['Introduction','Methods'])


@pytest.mark.asyncio
async def test_structured_section_transport_never_uses_the_freeform_heading_call():
 store=MemoryStore();contract=manuscript_contract('REVIEW','en');calls=[]
 async def unused(messages):raise AssertionError('Freeform transport must not be used')
 async def structured(headings,messages):
  assert 'Return one JSON object' in messages[0].content
  calls.append(headings)
  schema=group_schema(headings)
  return group_message(schema(title='',sections=[{'heading':h,'body':'### Scope\nOnly the provided evidence supports this limited interpretation.'} for h in headings]),headings)
 result=await write_section_groups({'research_question':'Question','report_length':'MEDIUM'},'Verified brief',contract,store,unused,structured_invoke=structured)
 assert len(calls)==len(section_groups(contract))
 assert '## Conclusion' in result.content


def test_short_keyword_sections_are_valid_without_allowing_outline_only_methods():
 from pydantic import ValidationError
 from app.services.sectional_writer import parse_group
 schema=group_schema(['Abstract','Keywords'],short_headings={'Keywords'})
 response=schema(title='',sections=[{'heading':'Abstract','body':'A substantive account of actual evidence and its limits.'},
                                  {'heading':'Keywords','body':'AI; ML; data'}])
 message=group_message(response,['Abstract','Keywords'])
 assert parse_group(message.content,['Abstract','Keywords'],{'Keywords'})['sections']['Keywords']=='AI; ML; data'
 with pytest.raises(ValidationError):group_schema(['Methods'])(title='',sections=[{'heading':'Methods','body':'Not known.'}])


@pytest.mark.asyncio
async def test_writer_node_uses_real_json_validation_and_renders_headings_for_personal_groups(monkeypatch):
 from types import SimpleNamespace
 from langchain_core.runnables import RunnableLambda
 from app.services import model_connection
 from app.services.manuscript import attach_manuscript_contract
 store=MemoryStore();calls=[]
 class Transport:
  max_tokens=8192
  extra_body={'provider':{'max_price':{'prompt':0,'completion':0,'request':0}}}
  def bind(self,**kwargs):
   assert kwargs['extra_body']['provider']['max_price']['completion']==0
   assert kwargs['extra_body']['response_format']['type']=='json_schema'
   async def send(messages):
    instruction=next(m.content for m in messages if 'order and spelling:' in m.content)
    headings=json.loads(re.search(r'order and spelling: (.+)\.',instruction.splitlines()[0])[1])
    calls.append(headings)
    def section(h):
     compact=h in {'Abstract','Keywords'}
     return {'heading':h,'body':'A compact summary of the recorded evidence and its limits.' if compact else '',
             'subsections':[] if compact else [
              {'heading':'Recorded scope','body':'Only the recorded evidence supports this bounded interpretation of the supplied research question.'},
              {'heading':'Interpretation and limits','body':'The available results permit a limited comparison and do not establish unrecorded generalization.'}]}
    return AIMessage(content=json.dumps({'title':'A measured study','sections':[section(h) for h in reversed(headings)]}),
     usage_metadata={'input_tokens':80,'output_tokens':40,'total_tokens':120},response_metadata={'finish_reason':'STOP'})
   return RunnableLambda(send)
 connection=SimpleNamespace(output_token_limit=8192,model_tag='byok:fixture',structured_output_mode='json_schema',estimate=lambda *_:0)
 monkeypatch.setattr(model_connection,'current_connection',lambda:connection)
 monkeypatch.setattr(CompletedWork,'for_state',lambda state:store)
 monkeypatch.setattr(nodes,'get_smart_llm',lambda:nodes.BudgetedFallbackLLM([('byok:fixture',Transport())]))
 monkeypatch.setattr(nodes,'get_active_model_name',lambda **kwargs:'byok:fixture')
 monkeypatch.setattr(nodes,'_record_progress',AsyncMock())
 monkeypatch.setattr(nodes,'record_agent_run',AsyncMock())
 state={'plan':attach_manuscript_contract({},'REVIEW','en'),'research_question':'Question','research_type':'REVIEW','report_length':'MEDIUM','language':'en'}
 result=await nodes.writer_node(state)
 assert re.findall(r'^## (.+)',result['draft_report_markdown'],re.M)==[s['heading'] for s in state['plan']['manuscript_contract']['sections']]
 assert len(calls)==len(section_groups(state['plan']['manuscript_contract']))
 assert all('[[@claim:' not in h for group in calls for h in group)


def test_structured_subsections_render_titles_and_paragraphs_on_separate_lines():
 from app.services.manuscript_structure import validate_hierarchy
 contract=manuscript_contract('EMPIRICAL_COMPUTATIONAL','en')
 schema=group_schema(['Methods'],layout={'Methods':{'minimum_subsections':2,'expand_after':100}})
 value=schema(title='',sections=[{'heading':'Methods','body':'','subsections':[
  {'heading':'Recorded method','body':'The recorded routine uses the supplied variables and preserves its documented assumptions and limits.'},
  {'heading':'Evaluation design','body':'The same recorded split is used for the measured model and baseline, without unexecuted procedures.'}]}])
 text=group_message(value,['Methods']).content
 assert '### Recorded method\n\nThe recorded' in text
 assert not any(f['code'] in {'EMPTY_SUBSECTION','UNDEVELOPED_SUBSECTION','SUBSECTION_STRUCTURE'} for f in validate_hierarchy(text,contract))


@pytest.mark.parametrize('bad',['### Scope All prose is incorrectly appended to this title.','Recorded values [[metrics:model]] establish the outcome.', 'Provenance [[manifest:input_checksum]] is supplied.'])
def test_structured_prose_rejects_inline_headings_and_invented_internal_citations(bad):
 from pydantic import ValidationError
 with pytest.raises(ValidationError):group_schema(['Methods'],layout={'Methods':{}})(title='',sections=[{'heading':'Methods','body':bad}])
