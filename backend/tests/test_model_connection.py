"""Custom API acceptance tests: ownership, isolation, secrets and no paid fallback."""
import asyncio
import json
import uuid
from copy import deepcopy

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.task import ResearchTask
from app.services.model_connection import (
    ModelConnectionInput, build_connection_client, connection_scope, current_connection,
    open_connection, seal_connection,
)
from app.services.provider_budget import ProviderBudgetExceeded, reserve_provider_call, settle_provider_call
from tests.test_provider_budget import create_running_task, delete_test_user

SECRET = "disposable-test-key-not-a-real-credential"


@pytest.mark.asyncio
async def test_api_catalog_is_public_even_with_an_expired_session_but_creation_is_private():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for headers in ({}, {'Authorization': 'Bearer expired-test-session'}):
            result = await client.get('/api/v1/research/model-connections/options', headers=headers)
            assert result.status_code == 200
            assert set(result.json()) == {'protocol', 'base_urls', 'use_server_providers', 'server_provider_ready', 'server_provider'}
            assert 'https://openrouter.ai/api/v1' in result.json()['base_urls']
        assert (await client.post('/api/v1/research', json={
            'title': 'Still requires login', 'research_question': 'Is research creation still private?'})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('finish,content,code', [
    ('length', '{"answer":"complete-looking but truncated"}', 'MODEL_OUTPUT_TRUNCATED'),
    ('stop', '', 'MODEL_INVALID_JSON'),
])
async def test_custom_json_does_not_accept_truncated_or_empty_output(finish, content, code):
    from langchain_core.runnables import RunnableLambda
    from langchain_core.messages import AIMessage
    from app.services.structured_output import compatible_structured_output
    class Result(BaseModel):
        answer: str
    class Model:
        extra_body = {'provider': {'max_price': {'prompt': 0, 'completion': 0}}}
        def bind(self, **kwargs):
            assert kwargs['extra_body']['provider']['max_price']['prompt'] == 0
            return RunnableLambda(lambda _: AIMessage(content=content, response_metadata={'finish_reason': finish}))
    with pytest.raises(ValueError, match=code):
        await compatible_structured_output('byok:test', Model(), Result).ainvoke([])


def test_public_errors_explain_truncation_without_exposing_secrets():
    from app.services.public_errors import public_error
    assert 'MODEL_OUTPUT_TRUNCATED' in public_error('LengthFinishReasonError ' + SECRET)
    assert 'PROVIDER_AUTH_FAILED' in public_error('HTTP 401 ' + SECRET)
    assert SECRET not in public_error('unexpected ' + SECRET)


@pytest.mark.asyncio
async def test_byok_budget_reserves_the_larger_output_limit(monkeypatch):
    from unittest.mock import AsyncMock
    from app.agents import nodes
    from langchain_core.messages import AIMessage
    model = AsyncMock()
    model.ainvoke.return_value = AIMessage(content='ok')
    reserve = AsyncMock(return_value='reservation')
    monkeypatch.setattr(nodes, 'reserve_provider_call', reserve)
    monkeypatch.setattr(nodes, 'settle_provider_call', AsyncMock())
    monkeypatch.setattr('app.services.provider_budget.assert_task_active', AsyncMock())
    await nodes.invoke_llm_with_budget({'enforce_provider_budget': True, 'task_id': str(uuid.uuid4()), 'attempt_number': 1},
        nodes.BudgetedFallbackLLM([('byok:test', model)]), [], model_name='byok:test', output_tokens=4096)
    assert reserve.await_args.kwargs['output_tokens'] == 8192


@pytest.mark.asyncio
async def test_length_error_does_not_blame_the_api_key():
    from unittest.mock import AsyncMock
    from app.agents.nodes import BudgetedFallbackLLM
    class LengthFinishReasonError(Exception):
        pass
    model = AsyncMock()
    model.ainvoke.side_effect = LengthFinishReasonError(SECRET)
    with pytest.raises(RuntimeError, match='MODEL_OUTPUT_TRUNCATED') as result:
        await BudgetedFallbackLLM([('byok:test', model)]).ainvoke([])
    assert SECRET not in str(result.value)


@pytest.mark.asyncio
@pytest.mark.parametrize('has_usage', [False, True])
async def test_schema_reservation_executes_and_usage_is_not_double_counted(monkeypatch, has_usage):
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage
    from app.agents import nodes
    class Output(BaseModel):
        answer: str
    response = AIMessage(content='answer', usage_metadata={'input_tokens': 500, 'output_tokens': 10, 'total_tokens': 510}) if has_usage else Output(answer='answer')
    model = AsyncMock()
    model.ainvoke.return_value = response
    reserve = AsyncMock(return_value='reservation')
    settle = AsyncMock()
    monkeypatch.setattr(nodes, 'reserve_provider_call', reserve)
    monkeypatch.setattr(nodes, 'settle_provider_call', settle)
    monkeypatch.setattr('app.services.provider_budget.assert_task_active', AsyncMock())
    token = nodes._BUDGET_CALL_CONTEXT.set({'task_id': str(uuid.uuid4()), 'attempt_number': 1,
        'input_tokens': 100, 'output_tokens': 100, 'prompt_text': 'A prompt'})
    try:
        await nodes.BudgetedFallbackLLM([('gpt-4o-mini', model)], structured_schema=Output).ainvoke([])
    finally:
        nodes._BUDGET_CALL_CONTEXT.reset(token)
    assert reserve.await_args.kwargs['input_tokens'] > 100
    assert settle.await_args.kwargs['succeeded']
    if has_usage:
        assert settle.await_args.kwargs['input_tokens'] == 500


@pytest.mark.asyncio
async def test_async_scope_waits_for_client_cleanup_even_when_failed():
    from unittest.mock import AsyncMock, Mock
    from app.services.model_connection import async_connection_scope
    tid, uid = uuid.uuid4(), uuid.uuid4()
    client = Mock(http_client=Mock(), http_async_client=Mock(aclose=AsyncMock()))
    with pytest.raises(RuntimeError):
        async with async_connection_scope({'_llm_connection': seal_connection(connection_input(), tid, uid)}, tid, uid):
            current_connection().register_client(client)
            raise RuntimeError('interrupted')
    assert current_connection() is None
    client.http_async_client.aclose.assert_awaited_once()
    client.http_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_create_endpoint_stores_encrypted_key_and_rejects_weak_server_secret(monkeypatch):
    tid, uid = await create_running_task()
    body = {'title': 'A private API task', 'research_question': 'How can a custom model support research?',
            'llm_connection': {'api_key': SECRET, 'base_url': 'https://api.groq.com/openai/v1', 'model': 'test-model'}}
    headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            result = await client.post('/api/v1/research', headers=headers, json=body)
            assert result.status_code == 201
            assert SECRET not in result.text
            async with AsyncSessionLocal() as db:
                task = await db.get(ResearchTask, uuid.UUID(result.json()['id']))
                assert SECRET not in json.dumps(task.budget_config)
                assert open_connection(task.budget_config, task.id, uid).api_key == SECRET
            # A short/default encryption key must not produce an unhandled 500.
            monkeypatch.setattr(settings, 'MOCK_PROVIDERS', False)
            monkeypatch.setattr(settings, 'APP_SECRET_KEY', 'short')
            headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
            rejected = await client.post('/api/v1/research', headers=headers, json=body)
            assert rejected.status_code == 503
            assert SECRET not in rejected.text
    finally:
        await delete_test_user(uid)


def connection_input(**patch):
    return ModelConnectionInput(api_key=SECRET, base_url="https://api.groq.com/openai/v1",
                                model="arbitrary-model-not-in-server-prices", **patch)


@pytest.mark.parametrize("root", ["http://localhost:9000/v1", "https://127.0.0.1/v1",
    "https://169.254.169.254/v1", "https://api.groq.com.evil.test/openai/v1",
    "https://api.groq.com/openai/v1?key=secret", "https://user@api.groq.com/openai/v1",
    "https://api.groq.com:444/openai/v1", "https://api.groq.com/redirect"])
def test_reject_untrusted_api_roots(root):
    with pytest.raises(ValidationError):
        ModelConnectionInput(api_key=SECRET, base_url=root, model="some-model")


def test_connection_is_encrypted_bound_to_task_and_owner_and_tamper_evident():
    task, owner = uuid.uuid4(), uuid.uuid4()
    stored = seal_connection(connection_input(), task, owner)
    assert SECRET not in json.dumps(stored)
    assert SECRET not in repr(connection_input())
    assert SECRET not in repr(open_connection({'_llm_connection': stored}, task, owner))
    assert open_connection({'_llm_connection': stored}, task, owner).api_key == SECRET
    for config, tid, uid in [({'_llm_connection': stored}, uuid.uuid4(), owner),
                              ({'_llm_connection': stored}, task, uuid.uuid4())]:
        with pytest.raises(ValueError, match="unavailable"):
            open_connection(config, tid, uid)
    tampered = deepcopy(stored)
    tampered['profile']['model'] = 'changed-model'
    with pytest.raises(ValueError, match="unavailable"):
        open_connection({'_llm_connection': tampered}, task, owner)


@pytest.mark.asyncio
async def test_context_isolated_across_concurrent_tasks_and_reset_on_error():
    async def use_model(name):
        tid, uid = uuid.uuid4(), uuid.uuid4()
        value = connection_input().model_copy(update={'model': name})
        with connection_scope({'_llm_connection': seal_connection(value, tid, uid)}, tid, uid):
            await asyncio.sleep(0)
            return current_connection().model
    assert await asyncio.gather(use_model('first'), use_model('second')) == ['first', 'second']
    assert current_connection() is None
    tid, uid = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(RuntimeError):
        with connection_scope({'_llm_connection': seal_connection(connection_input(), tid, uid)}, tid, uid):
            raise RuntimeError('test')
    assert current_connection() is None


@pytest.mark.asyncio
async def test_custom_client_uses_owner_key_model_json_schema_and_never_server_fallback(monkeypatch):
    from app.agents.nodes import build_llm_chain
    from app.services.agent_run import estimate_cost, get_active_model_name
    from app.services.model_connection import build_connection_client as real_builder
    from app.tools.embedder import EmbedderTool
    from app.services.structured_output import compatible_structured_output
    tid, uid = uuid.uuid4(), uuid.uuid4()
    value = connection_input(input_price_per_million=0.2, output_price_per_million=0.8)
    requests = []
    class Result(BaseModel):
        count: int = Field(ge=1)
    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion',
            'model': value.model, 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': '{"count":2}'}}],
            'usage': {'prompt_tokens': 30, 'completion_tokens': 5, 'total_tokens': 35}})
    transport = httpx.MockTransport(handler)
    client = real_builder(open_connection({'_llm_connection': seal_connection(value, tid, uid)}, tid, uid))
    await client.http_async_client.aclose()
    client.http_client.close()
    async with httpx.AsyncClient(transport=transport) as http_client:
        client.http_async_client = http_client
        from openai import AsyncOpenAI
        client.root_async_client = AsyncOpenAI(api_key=SECRET, base_url=value.base_url, http_client=http_client, max_retries=0)
        client.async_client = client.root_async_client.chat.completions
        monkeypatch.setattr('app.services.model_connection.build_connection_client', lambda _: client)
        with connection_scope({'_llm_connection': seal_connection(value, tid, uid)}, tid, uid):
            chain = build_llm_chain()
            assert len(chain.models) == 1
            assert get_active_model_name() == 'byok:' + value.model
            assert estimate_cost(get_active_model_name(), 1000, 1000) == 0.001
            assert EmbedderTool().embeddings is None
            answer = await chain.with_structured_output(Result).ainvoke([HumanMessage(content='Return count 2')])
            assert answer.count == 2
            from app.services.structured_output import StructuredOutputFailure
            with pytest.raises(StructuredOutputFailure, match='MODEL_INVALID_JSON'):
                invalid = client.model_copy()
                # Local Pydantic validation stays active for a custom endpoint.
                invalid_chain = compatible_structured_output('byok:test', invalid, Result)
                async def bad(request):
                    return httpx.Response(200, json={'id': 'test', 'choices': [{'index': 0,
                        'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"count":0}'}}]})
                with monkeypatch.context() as patch:
                    patch.setattr(transport, 'handle_async_request', bad)
                    await invalid_chain.ainvoke([HumanMessage(content='invalid result')])
    assert requests[0].url == value.base_url + '/chat/completions'
    assert requests[0].headers['authorization'] == 'Bearer ' + SECRET
    body = json.loads(requests[0].content)
    assert body['model'] == value.model
    assert body['response_format'] == {'type': 'json_object'}
    assert 'count' in body['messages'][0]['content']


@pytest.mark.asyncio
async def test_custom_provider_failure_is_sanitized_and_does_not_fallback(monkeypatch):
    from app.agents.nodes import BudgetedFallbackLLM
    class Broken:
        async def ainvoke(self, *_args, **_kwargs):
            raise RuntimeError('remote service echoed ' + SECRET)
    with pytest.raises(RuntimeError) as exc:
        await BudgetedFallbackLLM([('byok:test', Broken())]).ainvoke([])
    assert SECRET not in str(exc.value)
    assert 'API connection failed' in str(exc.value)


@pytest.mark.asyncio
async def test_custom_budget_no_server_spending_and_revocation_enforced_between_calls():
    tid, uid = await create_running_task()
    stored = seal_connection(connection_input(), tid, uid)
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, tid)
            task.budget_config = {**task.budget_config, '_llm_connection': stored}
            await db.commit()
        reservation = await reserve_provider_call(task_id=tid, attempt_number=1, kind='llm',
            model='byok:' + stored['profile']['model'], input_tokens=100, output_tokens=50)
        await settle_provider_call(task_id=tid, reservation_id=reservation, input_tokens=100,
            output_tokens=50, cost_usd=0, succeeded=True)
        for kwargs in [dict(kind='llm', model='gpt-4o'), dict(kind='embedding', model='text-embedding-3-small'),
                       dict(kind='search', fixed_cost_usd=.01)]:
            with pytest.raises(ProviderBudgetExceeded):
                await reserve_provider_call(task_id=tid, attempt_number=1, **kwargs)
        reservation = await reserve_provider_call(task_id=tid, attempt_number=1, kind='search', model='public:crossref', fixed_cost_usd=0)
        await settle_provider_call(task_id=tid, reservation_id=reservation, input_tokens=0, output_tokens=0, cost_usd=0, succeeded=True)
        headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            public = await client.get(f'/api/v1/research/{tid}', headers=headers)
            assert public.status_code == 200
            assert SECRET not in public.text and stored['secret'] not in public.text
            assert public.json()['total_cost_usd'] == 0
            assert public.json()['model_connection']['model'] == stored['profile']['model']
            assert (await client.delete(f'/api/v1/research/{tid}/model-connection')).status_code == 401
            assert (await client.delete(f'/api/v1/research/{tid}/model-connection', headers=headers)).status_code == 204
        with pytest.raises(ValueError, match='unavailable'):
            await reserve_provider_call(task_id=tid, attempt_number=1, kind='llm', model='byok:' + stored['profile']['model'])
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, tid)
            assert 'secret' not in task.budget_config['_llm_connection']
    finally:
        await delete_test_user(uid)


@pytest.mark.asyncio
async def test_validation_never_echoes_secret_even_for_nested_or_parent_errors():
    tid, uid = await create_running_task()
    try:
        headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            for connection in [dict(api_key=SECRET, base_url='https://127.0.0.1/v1', model='test'),
                               dict(api_key=SECRET, base_url='https://api.groq.com/openai/v1', model='bad model'),
                               [SECRET], SECRET]:
                response = await client.post('/api/v1/research', headers=headers, json={
                    'title': 'Custom connection', 'research_question': 'A valid research question?', 'llm_connection': connection})
                assert response.status_code == 422
                assert SECRET not in response.text
    finally:
        await delete_test_user(uid)


def test_free_openrouter_is_explicit_and_paid_routes_are_filtered():
    with pytest.raises(ValidationError):
        ModelConnectionInput(api_key=SECRET, base_url='https://openrouter.ai/api/v1', model='paid/model')
    tid, uid = uuid.uuid4(), uuid.uuid4()
    value = ModelConnectionInput(api_key=SECRET, base_url='https://openrouter.ai/api/v1', model='vendor/model:free')
    client = build_connection_client(open_connection({'_llm_connection': seal_connection(value, tid, uid)}, tid, uid))
    assert client.extra_body['provider']['max_price'] == {'prompt': 0, 'completion': 0, 'request': 0}
    assert client.cache is False
    assert client.extra_body['reasoning'] == {'effort': 'low', 'exclude': True}
    client.http_client.close()


@pytest.mark.asyncio
async def test_byok_error_handling_user_messages_and_no_leak():
    from unittest.mock import AsyncMock
    from app.agents.nodes import BudgetedFallbackLLM

    # 429 Rate limit
    mock_model_429 = AsyncMock()
    mock_model_429.ainvoke.side_effect = RuntimeError("Error 429: rate limit exceeded for this key sk-secret12345678")
    llm = BudgetedFallbackLLM([("byok:gpt-4o", mock_model_429)])
    with pytest.raises(RuntimeError) as exc_info:
        await llm.ainvoke("test")
    assert "rate limit or quota (HTTP 429)" in str(exc_info.value)
    assert "sk-secret12345678" not in str(exc_info.value)

    # 401 Unauthorized
    mock_model_401 = AsyncMock()
    mock_model_401.ainvoke.side_effect = RuntimeError("HTTP 401: unauthorized invalid api key sk-secret12345678")
    llm = BudgetedFallbackLLM([("byok:gpt-4o", mock_model_401)])
    with pytest.raises(RuntimeError) as exc_info:
        await llm.ainvoke("test")
    assert "rejected by the provider (HTTP 401)" in str(exc_info.value)
    assert "sk-secret12345678" not in str(exc_info.value)

    # 404 Model not found
    mock_model_404 = AsyncMock()
    mock_model_404.ainvoke.side_effect = RuntimeError("HTTP 404: model not found")
    llm = BudgetedFallbackLLM([("byok:nonexistent", mock_model_404)])
    with pytest.raises(RuntimeError) as exc_info:
        await llm.ainvoke("test")
    assert "model was not found on this provider (HTTP 404)" in str(exc_info.value)

    # Timeout
    mock_model_timeout = AsyncMock()
    mock_model_timeout.ainvoke.side_effect = TimeoutError("Request timed out")
    llm = BudgetedFallbackLLM([("byok:gpt-4o", mock_model_timeout)])
    with pytest.raises(RuntimeError) as exc_info:
        await llm.ainvoke("test")
    assert "PROVIDER_TIMEOUT" in str(exc_info.value)


@pytest.mark.asyncio
async def test_schema_extra_tokens_and_section_outline_prompt():
    from app.agents.nodes import BudgetedFallbackLLM, format_section_outline_prompt
    from pydantic import BaseModel, Field

    class DemoSchema(BaseModel):
        summary: str = Field(description="Summary")
        score: int = Field(description="Score")

    from unittest.mock import MagicMock
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = MagicMock()
    fallback = BudgetedFallbackLLM([("byok:demo", mock_model)])
    structured = fallback.with_structured_output(DemoSchema)
    assert structured.structured_schema is DemoSchema

    # Test format_section_outline_prompt
    outline = [
        {"section_id": "synthesis", "subsection_titles": ["Theme A", "Theme B"], "purpose": "Compare evidence"}
    ]
    prompt = format_section_outline_prompt(outline)
    assert "YÊU CẦU CẤU TRÚC TIÊU ĐỀ CON H3" in prompt
    assert "### Theme A" in prompt
    assert "### Theme B" in prompt
    assert "Compare evidence" in prompt

    # Empty outline returns empty string
    assert format_section_outline_prompt([]) == ""


@pytest.mark.asyncio
async def test_invalid_json_charges_reported_usage_without_claiming_success(monkeypatch):
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage
    from app.agents import nodes
    from app.services.structured_output import StructuredOutputFailure
    response = AIMessage(content='not JSON', usage_metadata={'input_tokens': 40, 'output_tokens': 5, 'total_tokens': 45})
    model = AsyncMock()
    model.ainvoke.side_effect = StructuredOutputFailure('MODEL_INVALID_JSON', response)
    reserve, settle = AsyncMock(return_value='reservation'), AsyncMock()
    monkeypatch.setattr(nodes, 'reserve_provider_call', reserve)
    monkeypatch.setattr(nodes, 'settle_provider_call', settle)
    monkeypatch.setattr('app.services.provider_budget.assert_task_active', AsyncMock())
    with pytest.raises(StructuredOutputFailure):
        await nodes.invoke_llm_with_budget({'enforce_provider_budget': True, 'task_id': str(uuid.uuid4()), 'attempt_number': 1},
            nodes.BudgetedFallbackLLM([('byok:test', model)]), [], model_name='byok:test')
    assert settle.await_args.kwargs['usage_reported'] is True
    assert settle.await_args.kwargs['succeeded'] is False
    assert settle.await_args.kwargs['output_tokens'] == 5


@pytest.mark.asyncio
async def test_json_node_reserves_its_actual_cap_instead_of_manuscript_limit(monkeypatch):
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage
    from app.agents import nodes
    model = AsyncMock()
    model.ainvoke.return_value = AIMessage(content='ok')
    reserve = AsyncMock(return_value='reservation')
    monkeypatch.setattr(nodes, 'reserve_provider_call', reserve)
    monkeypatch.setattr(nodes, 'settle_provider_call', AsyncMock())
    monkeypatch.setattr('app.services.provider_budget.assert_task_active', AsyncMock())
    await nodes.invoke_llm_with_budget({'enforce_provider_budget': True, 'task_id': str(uuid.uuid4()), 'attempt_number': 1},
        nodes.BudgetedFallbackLLM([('byok:test', model)], output_limits={'byok:test': 2048}), [], model_name='byok:test')
    assert reserve.await_args.kwargs['output_tokens'] == 2048

@pytest.mark.asyncio
async def test_byok_curator_monitor_does_not_claim_server_embedding_usage():
    from app.services.agent_run import record_agent_run
    from app.models.agent_run import AgentRun
    tid, uid = await create_running_task()
    try:
        with connection_scope({'_llm_connection': seal_connection(connection_input(), tid, uid)}, tid, uid):
            run_id = await record_agent_run(str(tid), 'Curator', model='gemini-embedding-2',
                input_tokens=1000, estimated_cost=0.01, output_summary={'chunks_indexed': 8})
        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            assert run.model == 'local-lexical-indexer'
            assert run.input_tokens == 0 and run.estimated_cost == 0
            assert run.output_summary['chunks_indexed'] == 8
    finally:
        await delete_test_user(uid)

@pytest.mark.asyncio
@pytest.mark.parametrize('model_name', ['byok:test', 'native-fixture'])
async def test_only_actual_provider_timeouts_get_the_recoverable_type(model_name):
    from unittest.mock import AsyncMock
    from app.agents.nodes import BudgetedFallbackLLM
    from app.services.public_errors import ProviderResponseTimeout
    model = AsyncMock()
    model.ainvoke.side_effect = TimeoutError('private transport details')
    with pytest.raises(ProviderResponseTimeout, match='PROVIDER_TIMEOUT') as caught:
        await BudgetedFallbackLLM([(model_name, model)]).ainvoke([])
    assert 'private transport details' not in str(caught.value)
