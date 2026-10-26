import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.grounding import Citation
from app.models.report import ReportVersion, ResearchReport
from app.models.report_question import ReportQuestion
from app.models.source import DocumentChunk, ResearchSource
from app.models.task import ResearchTask
from app.services import report_question_answering as answering
from app.services.report_question_answering import QuestionDraft


async def login(client):
    suffix = uuid.uuid4().hex[:12]
    email = f'qa_{suffix}@example.com'
    created = await client.post('/api/v1/auth/register', json={
        'username': f'qa_{suffix}', 'email': email, 'password': 'SecurePass123!',
    })
    assert created.status_code == 201, created.text
    response = await client.post('/api/v1/auth/login', json={'email': email, 'password': 'SecurePass123!'})
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


async def article(client, owner, evidence=True, max_calls=40):
    created = await client.post('/api/v1/research', headers=owner, json={
        'title': 'Version-pinned Q&A', 'research_question': 'What did the experiment measure?',
    })
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()['id'])
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        task.status = 'COMPLETED'
        task.attempt_number = 1
        task.budget_config = {'max_llm_calls': max_calls}
        report = ResearchReport(research_task_id=task_id)
        db.add(report)
        await db.flush()
        versions = []
        for number in (1, 2):
            version = ReportVersion(report_id=report.id, version_number=number,
                title=f'Version {number}', content_markdown=f'# Paper version {number}',
                review_metadata={'unchanged': number})
            db.add(version)
            await db.flush()
            versions.append(version.id)
            if evidence:
                source = ResearchSource(research_task_id=task_id, source_tag=f'src_0{number}',
                    url=f'https://example.com/v{number}', title=f'Study {number}')
                db.add(source)
                await db.flush()
                chunk = DocumentChunk(research_task_id=task_id, source_id=source.id,
                    chunk_index=0, content=f'The experiment in version {number} measured a reproducible numerical outcome.')
                db.add(chunk)
                await db.flush()
                db.add(Citation(research_task_id=task_id, report_id=report.id,
                    report_version_id=version.id, source_id=source.id, chunk_id=chunk.id,
                    citation_label='[1]', citation_number=1))
        await db.commit()
    return task_id, versions


class FakeModel:
    max_tokens = 4096
    cache = True

    def __init__(self, mode='valid', gate=None):
        self.calls = []
        self.mode = mode
        self.gate = gate

    def with_structured_output(self, schema):
        assert schema is QuestionDraft
        return self

    async def ainvoke(self, messages):
        data = json.loads(messages[1].content)
        self.calls.append(data)
        if self.gate:
            self.gate[0].set()
            await self.gate[1].wait()
        if self.mode == 'failure':
            raise RuntimeError('private-provider-api-key')
        evidence = data['saved_context']['evidence'][0]
        citation_id = str(uuid.uuid4()) if self.mode == 'invalid' else evidence['citation_id']
        quote = 'This quote was invented and is not in the saved document.' if self.mode == 'invented_quote' else evidence['excerpt']
        return QuestionDraft(answer='The saved study reports a measured numerical outcome.',
            insufficient_evidence=self.mode == 'insufficient',
            references=[{'citation_id': citation_id, 'quote': quote}])


def install(monkeypatch, model):
    monkeypatch.setattr(answering, 'question_models', lambda: [('gpt-4o-mini', model)])


def endpoint(task_id, version=1):
    return f'/api/v1/research/{task_id}/report/versions/{version}/questions'


@pytest.mark.asyncio
async def test_questions_pin_version_preserve_article_and_enforce_ownership(monkeypatch):
    model = FakeModel()
    install(monkeypatch, model)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner, other = await login(client), await login(client)
        task_id, versions = await article(client, owner)
        payload = {'request_id': str(uuid.uuid4()), 'question': 'What did the experiment measure?'}
        url = endpoint(task_id)
        assert (await client.post(url, json=payload)).status_code == 401
        assert (await client.post(url, json=payload, headers=other)).status_code == 404
        response = await client.post(url, json=payload, headers=owner)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == 'ANSWERED' and result['report_version_id'] == str(versions[0])
        assert result['references'][0]['source_url'] == 'https://example.com/v1'
        assert 'version 1' in result['references'][0]['quote']
        assert model.calls[0]['saved_context']['article_excerpt'] == '# Paper version 1'
        assert model.max_tokens == 1024 and model.cache is False
        assert response.headers['cache-control'] == 'private, no-store'
        assert (await client.post(url, json=payload, headers=owner)).json()['id'] == result['id']
        assert len(model.calls) == 1
        assert (await client.post(endpoint(task_id, 2), json=payload, headers=owner)).status_code == 409
        assert (await client.post(url, json={**payload, 'question': 'Different question?'}, headers=owner)).status_code == 409
        newer = await client.post(endpoint(task_id, 2), headers=owner, json={**payload, 'request_id': str(uuid.uuid4())})
        assert newer.status_code == 200, newer.text
        assert newer.json()['report_version_id'] == str(versions[1])
        history = await client.get(url, headers=owner)
        assert history.json()['total'] == 1
        assert history.json()['items'][0]['id'] == result['id']
        assert (await client.get(url, headers=other)).status_code == 404
        assert (await client.get(endpoint(task_id, 99), headers=owner)).status_code == 404
        assert (await client.get(url + '?limit=101', headers=owner)).status_code == 422
        assert (await client.post(url, headers=owner, json={**payload, 'question': ' '})).status_code == 422
        async with AsyncSessionLocal() as db:
            for number, version_id in enumerate(versions, 1):
                saved = await db.get(ReportVersion, version_id)
                assert saved.content_markdown == f'# Paper version {number}'
                assert saved.review_metadata == {'unchanged': number}
            task = await db.get(ResearchTask, task_id)
            assert task.status == 'COMPLETED' and task.budget_config['_provider_usage']['llm_calls'] == 2
            assert (await db.scalar(select(func.count(Citation.id)).where(Citation.research_task_id == task_id))) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(('mode', 'expected', 'error'), [
    ('invalid', 'FAILED', 'INVALID_REFERENCE'),
    ('invented_quote', 'FAILED', 'INVALID_REFERENCE'),
    ('failure', 'FAILED', 'PROVIDER_ERROR'),
    ('insufficient', 'INSUFFICIENT_EVIDENCE', None),
])
async def test_questions_fail_closed_and_keep_safe_history(monkeypatch, mode, expected, error):
    install(monkeypatch, FakeModel(mode))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, _ = await article(client, owner)
        response = await client.post(endpoint(task_id), headers=owner, json={
            'request_id': str(uuid.uuid4()), 'question': 'What evidence supports the result?',
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == expected and result['error_code'] == error
        assert result['references'] == []
        assert 'private-provider-api-key' not in response.text
        if expected == 'FAILED':
            assert result['answer'] is None
        else:
            assert 'Chưa đủ bằng chứng' in result['answer']
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            assert task.budget_config['_provider_usage']['reservations'] == {}


@pytest.mark.asyncio
async def test_empty_evidence_and_exhausted_budget_make_no_provider_request(monkeypatch):
    model = FakeModel()
    install(monkeypatch, model)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        for evidence, max_calls, expected in [(False, 40, 'INSUFFICIENT_EVIDENCE'), (True, 0, 'BUDGET_LIMIT')]:
            task_id, _ = await article(client, owner, evidence=evidence, max_calls=max_calls)
            response = await client.post(endpoint(task_id), headers=owner, json={
                'request_id': str(uuid.uuid4()), 'question': 'What did the experiment measure?',
            })
            assert response.status_code == 200, response.text
            assert response.json()['status'] == expected
        assert model.calls == []


@pytest.mark.asyncio
async def test_active_question_deduplicates_requests_and_drops_late_deleted_result(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    model = FakeModel(gate=(started, release))
    install(monkeypatch, model)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, _ = await article(client, owner)
        payload = {'request_id': str(uuid.uuid4()), 'question': 'What was measured?'}
        pending = asyncio.create_task(client.post(endpoint(task_id), headers=owner, json=payload))
        try:
            await asyncio.wait_for(started.wait(), 10)
            duplicate = await client.post(endpoint(task_id), headers=owner, json=payload)
            assert duplicate.status_code == 200, duplicate.text
            assert duplicate.json()['status'] == 'RUNNING'
            other = await client.post(endpoint(task_id), headers=owner, json={**payload, 'request_id': str(uuid.uuid4())})
            assert other.status_code == 409
            second_task, _ = await article(client, owner)
            another_article = await client.post(endpoint(second_task), headers=owner,
                json={**payload, 'request_id': str(uuid.uuid4())})
            assert another_article.status_code == 409
            assert len(model.calls) == 1
            async with AsyncSessionLocal() as db:
                task = await db.get(ResearchTask, task_id)
                task.status = 'DELETING'
                await db.commit()
            release.set()
            assert (await pending).status_code == 404
            assert (await client.get(endpoint(task_id), headers=owner)).status_code == 404
        finally:
            release.set()
            await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_expired_question_is_recovered_and_deleted_with_report(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, versions = await article(client, owner)
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            q = ReportQuestion(user_id=task.user_id, report_version_id=versions[0], request_id=uuid.uuid4(),
                question='Interrupted question', status='RUNNING', expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            db.add(q)
            await db.commit()
            question_id = q.id
        response = await client.get(endpoint(task_id), headers=owner)
        assert response.status_code == 200, response.text
        assert response.json()['items'][0]['error_code'] == 'INTERRUPTED'
        async with AsyncSessionLocal() as db:
            version = await db.get(ReportVersion, versions[0])
            await db.delete(version)
            await db.commit()
            assert await db.get(ReportQuestion, question_id) is None


@pytest.mark.asyncio
async def test_post_run_question_budget_does_not_enable_normal_calls(monkeypatch):
    from app.services.provider_budget import ResearchTaskStopped, reserve_provider_call
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, _ = await article(client, owner)
        with pytest.raises(ResearchTaskStopped):
            await reserve_provider_call(task_id=task_id, attempt_number=1, kind='llm',
                model='gpt-4o-mini', input_tokens=10, output_tokens=10)
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            task.status = 'CANCELLED'
            await db.commit()
        with pytest.raises(ResearchTaskStopped):
            await reserve_provider_call(task_id=task_id, attempt_number=1, kind='llm',
                model='gpt-4o-mini', input_tokens=10, output_tokens=10, allow_post_run=True)


@pytest.mark.asyncio
async def test_question_timeout_reconciles_budget_and_releases_active_slot(monkeypatch):
    from app.services import report_questions as service
    started, release = asyncio.Event(), asyncio.Event()
    install(monkeypatch, FakeModel(gate=(started, release)))
    monkeypatch.setattr(service, 'QA_TIMEOUT_SECONDS', 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, _ = await article(client, owner)
        response = await client.post(endpoint(task_id), headers=owner, json={
            'request_id': str(uuid.uuid4()), 'question': 'What was measured in the experiment?',
        })
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'FAILED' and response.json()['error_code'] == 'TIMEOUT'
        assert started.is_set()
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            usage = task.budget_config.get('_provider_usage', {})
            assert usage.get('reservations', {}) == {}
            assert await db.scalar(select(func.count(ReportQuestion.id)).where(
                ReportQuestion.user_id == task.user_id, ReportQuestion.status == 'RUNNING')) == 0


@pytest.mark.asyncio
async def test_changed_task_state_in_same_session_cannot_publish_answer(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    install(monkeypatch, FakeModel(gate=(started, release)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, _ = await article(client, owner)
        pending = asyncio.create_task(client.post(endpoint(task_id), headers=owner, json={
            'request_id': str(uuid.uuid4()), 'question': 'What was measured?',
        }))
        try:
            await asyncio.wait_for(started.wait(), 10)
            async with AsyncSessionLocal() as db:
                task = await db.get(ResearchTask, task_id)
                task.status = 'CANCELLED'
                task.attempt_number += 1
                await db.commit()
            release.set()
            response = await pending
            assert response.status_code == 200, response.text
            assert response.json()['status'] == 'FAILED'
            assert response.json()['error_code'] == 'TASK_CHANGED'
            assert response.json()['answer'] is None
        finally:
            release.set()
            await asyncio.gather(pending, return_exceptions=True)


def test_reference_validator_rejects_other_version_id_and_unmatched_quotes():
    from app.services.report_question_answering import InvalidAnswer, validate_answer
    allowed, other = str(uuid.uuid4()), str(uuid.uuid4())
    context = {'evidence': [{'citation_id': allowed, 'title': 'Source', 'url': 'https://example.com',
                             'excerpt': 'This exact quotation belongs only to the selected report version.'}]}
    with pytest.raises(InvalidAnswer):
        validate_answer(QuestionDraft(answer='A conclusion', insufficient_evidence=False,
            references=[{'citation_id': other, 'quote': context['evidence'][0]['excerpt']}]), context)
    with pytest.raises(InvalidAnswer):
        validate_answer(QuestionDraft(answer='A conclusion', insufficient_evidence=False,
            references=[{'citation_id': allowed, 'quote': 'This quotation was never saved in the selected version.'}]), context)


def test_bounded_context_can_find_relevant_text_at_end_of_long_paragraph():
    from app.services.report_question_answering import bounded_excerpt
    text = ('Background material. ' * 1000) + 'Uncertainty reduction was the important final outcome.'
    excerpt = bounded_excerpt(text, 'What was the uncertainty reduction outcome?', 1200)
    assert len(excerpt) <= 1200
    assert 'Uncertainty reduction' in excerpt


@pytest.mark.asyncio
async def test_article_question_limit_applies_across_versions_and_history_is_paginated(monkeypatch):
    model = FakeModel()
    install(monkeypatch, model)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        owner = await login(client)
        task_id, versions = await article(client, owner)
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            now = datetime.now(timezone.utc)
            db.add_all([ReportQuestion(user_id=task.user_id, report_version_id=versions[0],
                request_id=uuid.uuid4(), question=f'Saved question {index}', status='INSUFFICIENT_EVIDENCE',
                expires_at=now, completed_at=now) for index in range(50)])
            await db.commit()
        response = await client.post(endpoint(task_id, 2), headers=owner, json={
            'request_id': str(uuid.uuid4()), 'question': 'What did the study measure?',
        })
        assert response.status_code == 429
        assert model.calls == []
        history = (await client.get(endpoint(task_id) + '?offset=40&limit=20', headers=owner)).json()
        assert history['total'] == 50 and len(history['items']) == 10
