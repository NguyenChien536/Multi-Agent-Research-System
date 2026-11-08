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
