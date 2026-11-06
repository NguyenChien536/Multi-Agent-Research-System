import json
import uuid
import httpx
import pytest
from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.task import ResearchTask
from app.models.user import User
from app.services.model_connection import open_connection
from app.api.v1.endpoints.settings import decode_input, settings_id
from tests.test_provider_budget import create_running_task, delete_test_user

KEY = 'fake-settings-credential-not-real'
VALUE = {'api_key': KEY, 'base_url': 'https://api.groq.com/openai/v1', 'model': 'test-model', 'output_token_limit':16384, 'reasoning_effort':'low'}

@pytest.mark.asyncio
async def test_saved_model_defaults_are_encrypted_private_and_snapshotted_per_task():
    tid, uid = await create_running_task()
    other_tid, other_uid = await create_running_task()
    headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
    other = {'Authorization': 'Bearer ' + create_access_token(other_uid)}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/api/v1/settings/model-connection')).status_code == 401
            assert (await client.get('/api/v1/settings/model-connection', headers=headers)).json()['connection'] is None
            saved = await client.put('/api/v1/settings/model-connection', json=VALUE, headers=headers)
            assert saved.status_code == 200 and KEY not in saved.text
            assert saved.json()['connection']['has_key']
            assert saved.json()['connection']['output_token_limit'] == 16384
            assert (await client.get('/api/v1/settings/model-connection', headers=other)).json()['connection'] is None
            async with AsyncSessionLocal() as db:
                user = await db.get(User, uid)
                assert KEY not in json.dumps(user.model_connection)
                assert decode_input(user.model_connection, uid, settings_id(uid)).api_key.get_secret_value() == KEY
            created = await client.post('/api/v1/research', json={'title':'Saved-model research', 'research_question':'How can research preserve model configuration?'}, headers=headers)
            assert created.status_code == 201 and KEY not in created.text
            created_id = uuid.UUID(created.json()['id'])
            assert created.json()['model_connection']['model'] == 'test-model'
            # Change the default model while keeping the write-only saved key.
            changed = {k:v for k,v in VALUE.items() if k != 'api_key'} | {'model':'new-model'}
            assert (await client.put('/api/v1/settings/model-connection', json=changed, headers=headers)).status_code == 200
            async with AsyncSessionLocal() as db:
                task = await db.get(ResearchTask, created_id)
                assert open_connection(task.budget_config, task.id, uid).model == 'test-model'
                assert open_connection(task.budget_config, task.id, uid).api_key == KEY
            assert (await client.put('/api/v1/settings/model-connection', json={**changed,'base_url':'https://api.mistral.ai/v1'}, headers=headers)).status_code == 400
            assert (await client.post(f'/api/v1/settings/research/{tid}/use-default', headers=headers)).status_code == 409
            assert (await client.post(f'/api/v1/settings/research/{created_id}/use-default', headers=other)).status_code == 404
            assert (await client.post(f'/api/v1/settings/research/{created_id}/use-default', headers=headers)).status_code == 200
            assert (await client.get(f'/api/v1/research/{created_id}', headers=headers)).json()['model_connection']['model'] == 'new-model'
            assert (await client.delete('/api/v1/settings/model-connection', headers=headers)).status_code == 204
            assert (await client.get('/api/v1/settings/model-connection', headers=headers)).json()['connection'] is None
            assert (await client.get(f'/api/v1/research/{created_id}', headers=headers)).json()['model_connection']['model'] == 'new-model'
            assert (await client.post(f'/api/v1/settings/research/{created_id}/save-as-default', headers=other)).status_code == 404
            copied = await client.post(f'/api/v1/settings/research/{created_id}/save-as-default', headers=headers)
            assert copied.status_code == 200 and KEY not in copied.text
            assert (await client.get('/api/v1/settings/model-connection', headers=headers)).json()['connection']['model'] == 'new-model'
    finally:
        await delete_test_user(uid)
        await delete_test_user(other_uid)

@pytest.mark.asyncio
async def test_settings_invalid_input_does_not_echo_key():
    tid, uid = await create_running_task()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            result = await client.put('/api/v1/settings/model-connection', headers={'Authorization':'Bearer '+create_access_token(uid)},
                json={**VALUE,'input_price_per_million':'invalid'})
            assert result.status_code == 422 and KEY not in result.text
    finally:
        await delete_test_user(uid)

@pytest.mark.parametrize('kind', ['REVIEW','EMPIRICAL_COMPUTATIONAL','EMPIRICAL_HUMAN'])
def test_manuscript_skeleton_has_genre_specific_children_without_invented_results(kind):
    from app.services.academic_writing import manuscript_skeleton
    from app.services.manuscript import manuscript_contract
    text = manuscript_skeleton(manuscript_contract(kind,'en'), [{'section_id':'discussion','subsection_titles':['Assumptions and Scope','Evidence Gaps']}])
    assert '### Assumptions and Scope' in text
    assert '### Research Questions, Scope and Contributions' in text
    if kind == 'REVIEW':
        assert '### Source Selection and Synthesis Procedure' in text
        assert '### Observed Outcomes' not in text
    else:
        assert '### Observed Outcomes' in text
    assert 'p-value' not in text and 'significantly better' not in text

@pytest.mark.asyncio
async def test_writer_does_not_call_model_without_evidence_in_a_real_run(monkeypatch):
    from unittest.mock import AsyncMock, Mock
    from app.agents import nodes
    from app.services.evidence_policy import InsufficientEvidence
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    factory = Mock()
    monkeypatch.setattr(nodes, 'get_smart_llm', factory)
    with pytest.raises(InsufficientEvidence):
        await nodes.writer_node({'task_id':str(uuid.uuid4()),'enforce_provider_budget':True,'claims':[]})
    factory.assert_not_called()

def test_evidence_gate_needs_provenance_not_just_plausible_text():
    from app.services.evidence_policy import has_writing_evidence
    assert not has_writing_evidence({'claims':[{'claim':'A plausible assertion','evidence_quote':'Some text'}]})
    assert has_writing_evidence({'claims':[{'claim_id':'c','evidence_id':'e','source_id':'s','chunk_id':'p','claim':'Bounded claim','evidence_quote':'Exact quote'}]})
    assert not has_writing_evidence({'analysis_run':{'status':'FAILED','metrics':{'accuracy':1}}})

def test_pdf_extraction_normalizes_nul_before_database_storage(monkeypatch):
    from types import SimpleNamespace
    from app.services import pdf_parser
    reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda:'A source paragraph with a NUL\x00 between words and enough readable text.')],
                             metadata=SimpleNamespace(title='Test\x00title', author='Test\x00author'))
    monkeypatch.setattr(pdf_parser, 'PdfReader', lambda *_args, **_kwargs: reader)
    result = pdf_parser.extract_text_from_pdf(b'%PDF-1.4\nfixture')
    assert '\x00' not in result['text'] and 'NUL  between' in result['text']
    assert result['title'] == 'Test title' and result['author'] == 'Test author'

def test_previous_encrypted_connections_remain_readable_after_model_options_added():
    from app.services.model_connection import ModelConnectionInput, seal_connection, open_connection, _cipher
    tid, uid = uuid.uuid4(), uuid.uuid4()
    value = ModelConnectionInput(**VALUE)
    stored = seal_connection(value, tid, uid)
    payload = json.loads(_cipher().decrypt(stored['secret'].encode()))
    for key in ('output_token_limit','reasoning_effort'):
        stored['profile'].pop(key)
        payload.pop(key)
    stored['secret'] = _cipher().encrypt(json.dumps(payload).encode()).decode()
    restored = open_connection({'_llm_connection':stored}, tid, uid)
    assert restored.api_key == KEY and restored.output_token_limit == 8192

@pytest.mark.asyncio
async def test_catalog_only_lists_free_json_models_and_never_sends_credentials(monkeypatch):
    from app.services import model_catalog
    monkeypatch.setattr(model_catalog, '_cache', None)
    monkeypatch.setattr(model_catalog, '_expires', 0)
    rows = [
        {'id':'test/json:free','pricing':{'prompt':'0','completion':'0'},'supported_parameters':['response_format']},
        {'id':'test/paid','pricing':{'prompt':'1','completion':'2'},'supported_parameters':['response_format']},
        {'id':'test/no-json:free','pricing':{'prompt':'0','completion':'0'},'supported_parameters':[]},
    ]
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'data':rows}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,**kwargs):
            assert url == 'https://openrouter.ai/api/v1/models'
            assert 'headers' not in kwargs
            return Reply()
    monkeypatch.setattr(model_catalog.httpx, 'AsyncClient', lambda **kwargs: Client())
    assert [row['id'] for row in await model_catalog.free_models()] == ['test/json:free']
