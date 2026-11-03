import re
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.models.source import ResearchSource, DocumentChunk
from app.models.task import ResearchTask
from app.models.user import User
from app.services.evidence_selection import (
    analysis_needs, evidence_need_coverage, fuse_diverse_chunks, spread_indexes, query_terms, rank_discovery_candidates,
    blocking_evidence_gaps,
    metadata_triage_order,
)
from app.services.grounding import persist_grounded_claims, source_quote_span
from app.tools.embedder import EmbedderTool


@pytest_asyncio.fixture
async def corpus():
    user_id, task_id = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(id=user_id, username='coverage_'+user_id.hex[:10], email=user_id.hex+'@example.com', password_hash='test'))
        await db.flush()
        db.add(ResearchTask(id=task_id, user_id=user_id, title='Evidence coverage fixture', research_question='What does the collected evidence support?'))
        await db.flush()
        sources, chunks = [], []
        for i, content in enumerate([
            'Ocean salinity and marine fisheries were studied in coastal waters.',
            'Ridge regression reduced prediction error against the mean baseline in this dataset.',
            'Ridge regression has limitations under distribution shift; causal effects were not tested.',
        ]):
            source = ResearchSource(research_task_id=task_id, source_tag=f'src_{i}', title=f'Fixture {i}',
                                    url=f'https://example.org/{i}', text_scope='FULL_TEXT')
            db.add(source)
            await db.flush()
            chunk = DocumentChunk(research_task_id=task_id, source_id=source.id, chunk_index=i*20, content=content)
            db.add(chunk)
            sources.append(source)
            chunks.append(chunk)
        await db.commit()
    yield task_id, sources, chunks
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        await db.delete(user)
        await db.commit()


def test_sampling_keeps_late_results_and_diversity_without_inventing_candidates():
    assert spread_indexes(200, 128)[-1] == 199
    assert len(set(spread_indexes(200, 128))) == 128
    assert spread_indexes(20, 8)[-1] == 19
    chunks = [SimpleNamespace(id=str(i), source_id='a' if i<5 else 'b', chunk_index=i) for i in range(6)]
    result = fuse_diverse_chunks([(c, .1) for c in chunks], [], 3)
    assert {c.source_id for c, _ in result} == {'a', 'b'}
    assert len(result) == 3
    assert fuse_diverse_chunks([], [], 3) == []
    assert query_terms("Ridge & ('regression') | ! 2026") == ['ridge', 'regression', '2026']


def test_whitespace_alignment_returns_original_source_and_never_repairs_words_or_punctuation():
    source='Limited\n  evidence\u00a0supports the result.'
    assert source_quote_span(source, 'Limited evidence supports the result.') == source
    assert source_quote_span(source, 'Strong evidence supports the result.') is None
    assert source_quote_span(source, 'limited evidence supports the result.') is None
    assert source_quote_span(source, 'Limited evidence supports the result!') is None
    assert source_quote_span(source, '   ') is None


@pytest.mark.asyncio
async def test_storage_keeps_body_text_but_bounds_embedding_calls():
    tool = object.__new__(EmbedderTool)
    docs = [SimpleNamespace(page_content=f'Original document section {i}') for i in range(200)]
    tool.chunk_text = lambda _content: docs
    tool.embeddings = None
    stored = []
    count = await tool.embed_and_store(SimpleNamespace(add_all=stored.extend), uuid.uuid4(), uuid.uuid4(), 'fixture')
    assert count == 128
    assert stored[-1].content == 'Original document section 199'
    assert stored[-1].chunk_index == 199
    assert all(c.embedding is None for c in stored)


def test_discovery_ranks_metadata_without_excluding_uncertain_foundational_titles():
    from app.tools.search_models import SearchResult
    items = [SearchResult(title='Marine ecosystems', url='https://example.org/ocean', query='ridge baseline', content='Unrelated fisheries data.'),
             SearchResult(title='Ridge regression baseline', url='https://example.org/ridge', query='ridge baseline'),
             SearchResult(title='A foundational result', url='https://example.org/foundation', query='ridge baseline')]
    ranked = rank_discovery_candidates(items)
    assert ranked[0].title == 'Ridge regression baseline'
    assert len(ranked) == 3


def test_metadata_triage_prioritizes_primary_candidates_and_preserves_unknown_items():
    from app.tools.search_models import SearchResult
    items = [SearchResult(title=f'Candidate {i}', url=f'https://example.org/{i}') for i in range(4)]
    ranked, log = metadata_triage_order(items, [
        dict(candidate_id='c01', relevance='DIRECT', study_role='GUIDE', reason='Practitioner guide'),
        dict(candidate_id='c02', relevance='DIRECT', study_role='PRIMARY', reason='Metadata indicates an original evaluation'),
        dict(candidate_id='c03', relevance='DIRECT', study_role='PRIMARY', reason='Conflicting duplicate'),
        dict(candidate_id='c03', relevance='OUT_OF_SCOPE', study_role='GUIDE', reason='Conflicting duplicate'),
        dict(candidate_id='c04', relevance='CONTEXT', study_role='REVIEW', reason='Adjacent vertical application'),
        dict(candidate_id='invented', relevance='DIRECT', study_role='PRIMARY', reason='Unknown ID ignored')])
    assert ranked[0] == items[1]
    assert len(ranked) == 4 and len(log) == 4
    assert log[2]['relevance'] == 'UNCERTAIN' and not log[2]['metadata_assessment_present']


def test_metadata_assessments_keep_candidate_identity_when_landing_urls_overlap():
    from app.tools.search_models import SearchResult
    items = [SearchResult(title=title, url='https://example.org/shared') for title in ('Guide', 'Original study')]
    ranked, rows = metadata_triage_order(items, [
        dict(candidate_id='c01', relevance='DIRECT', study_role='GUIDE', reason='Guide'),
        dict(candidate_id='c02', relevance='DIRECT', study_role='PRIMARY', reason='Study')])
    assert ranked == [items[1], items[0]]
    assert [row['candidate_id'] for row in rows] == ['c01', 'c02']


@pytest.mark.asyncio
@pytest.mark.parametrize('triage_mode', ['assessed', 'unavailable', 'budget_exhausted'])
async def test_researcher_applies_bounded_metadata_triage_before_fetch_and_source_cap(monkeypatch, triage_mode):
    import json
    from app.agents import nodes
    from app.tools import search, scraper
    from app.tools.search_models import SearchResult
    candidates = [SearchResult(title='RAG citation practitioner guide', url='https://example.org/guide', query='RAG citation', content='Citation recommendations.'),
                  SearchResult(title='Original citation evaluation', url='https://example.org/primary', query='RAG citation', content='We evaluated factual support and attribution on benchmark outputs.')]
    monkeypatch.setattr(search, 'execute_parallel_searches', AsyncMock(return_value=(candidates, [])))
    monkeypatch.setattr(scraper, 'fetch_urls_parallel', AsyncMock(return_value={str(c.url):c.content for c in candidates}))
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    monkeypatch.setattr(nodes, 'get_fast_llm', lambda: SimpleNamespace(with_structured_output=lambda _:object()))
    from app.services import provider_budget
    monkeypatch.setattr(provider_budget, 'assert_task_active', AsyncMock())
    async def assess(_state, _model, messages, **kwargs):
        if triage_mode == 'unavailable':
            raise RuntimeError('Provider temporarily unavailable')
        if triage_mode == 'budget_exhausted':
            raise provider_budget.ProviderBudgetExceeded('No budget for metadata triage')
        payload=json.loads(messages[0].content.split('<candidates>')[1].split('</candidates>')[0])
        assert len(payload) <= 24
        return nodes.SourceTriage(assessments=[nodes.MetadataAssessment(candidate_id=c['candidate_id'], relevance='DIRECT',
            study_role='PRIMARY' if 'Original' in c['title'] else 'GUIDE', reason='Metadata-only fixture judgment') for c in payload])
    monkeypatch.setattr(nodes, 'invoke_llm_with_budget', assess)
    state={'task_id':str(uuid.uuid4()), 'attempt_number':1, 'enforce_provider_budget':True,
           'research_question':'How accurate are RAG citations?', 'max_sources':1, 'delta_queries':['RAG citation'],
           'plan':{'evidence_needs':[dict(need_id='citation', question='What evidence supports citations?')]}}
    if triage_mode == 'budget_exhausted':
        with pytest.raises(provider_budget.ProviderBudgetExceeded):
            await nodes.researcher_node(state)
        scraper.fetch_urls_parallel.assert_not_awaited()
        return
    result=await nodes.researcher_node(state)
    if triage_mode == 'unavailable':
        assert result['collected_sources'][0]['url'] == 'https://example.org/guide'
        assert result['source_selection_log'][0]['status'] == 'UNAVAILABLE'
        assert result['source_selection_log'][0]['error_type'] == 'RuntimeError'
        return
    assert result['collected_sources'][0]['url']=='https://example.org/primary'
    assert result['source_selection_log'][0]['status']=='ASSESSED'
    assert 'not full-text' in result['source_selection_log'][0]['scope']


def test_legacy_and_duplicate_needs_are_bounded_and_gaps_are_not_claimed_covered():
    assert len(analysis_needs({'current_queries': ['q'] * 8})) == 1
    needs = analysis_needs({'plan': {'evidence_needs': [
        dict(need_id='same', question='Question A', search_query='A', section_id='synthesis'),
        dict(need_id='same', question='Question B', search_query='B', section_id='discussion')]}})
    assert len({n['need_id'] for n in needs}) == 2
    collided = analysis_needs({'plan': {'evidence_needs': [
        dict(need_id='need_2', question='First'), dict(need_id='need_2', question='Second')]}})
    assert len({n['need_id'] for n in collided}) == 2
    coverage = evidence_need_coverage(needs, [([], []), ([], [])])
    assert len(coverage['missing_need_ids']) == 2
    assert len(evidence_need_coverage(needs, [([], [])])['missing_need_ids']) == 2
    contextual = {'missing_need_ids':['limits'], 'needs':[{'need_id':'limits', 'role':'COUNTEREVIDENCE'}]}
    assert blocking_evidence_gaps(contextual) == []
    assert blocking_evidence_gaps({'missing_need_ids':['unknown']}) == ['unknown']


@pytest.mark.asyncio
async def test_writer_receives_supported_sources_assumptions_and_explicit_gaps(monkeypatch):
    from app.agents import nodes
    captured = []
    class Writer:
        async def ainvoke(self, messages):
            captured.append(messages[0].content)
            return SimpleNamespace(content='## Discussion\n\nEvidence remains limited.')
    monkeypatch.setattr(nodes, 'get_smart_llm', lambda: Writer())
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    cid = str(uuid.uuid4())
    await nodes.writer_node({'research_question':'What can we conclude?', 'plan': {}, 'claims': [
        dict(claim_id=cid, evidence_id='e', source_id='s', claim='Limited prediction result',
             evidence_quote='The held-out result.', source_title='Original study', text_scope='ABSTRACT',
             evidence_need_id='results', assumptions=['Only this held-out dataset'])],
        'evidence_need_coverage': {'missing_need_ids':['causality']}})
    assert 'Original study' in captured[0] and 'Only this held-out dataset' in captured[0]
    assert 'causality' in captured[0] and 'Do not invent' in captured[0]


@pytest.mark.asyncio
async def test_quote_gap_cannot_be_marked_completed_by_positive_critic(monkeypatch):
    from app.agents import nodes
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    result = await nodes.post_processor_node({'plan': {'evidence_needs': [{'need_id':'missing'}]},
        'draft_report_markdown':'# Draft\n\nA question remains open.', 'critic_verdict':'PASS',
        'critic_review_metadata':{'status':'PASSED'},
        'evidence_need_coverage':{'missing_need_ids':['missing']}})
    assert result['status'] == 'NEEDS_REVIEW'
    assert result['critic_review_metadata']['evidence_need_findings']


@pytest.mark.asyncio
async def test_lexical_fallback_finds_late_methods_and_ignores_unrelated_prefix(corpus):
    tid, sources, chunks = corpus
    tool = object.__new__(EmbedderTool)
    tool.embeddings = None
    async with AsyncSessionLocal() as db:
        result = await tool.search_similar_chunks(db, tid, 'Ridge regression prediction limitations', limit=2)
        assert {c.id for c, _ in result} == {chunks[1].id, chunks[2].id}
        assert await tool.search_similar_chunks(db, tid, 'quantum entanglement', limit=3) == []
        assert await tool.search_similar_chunks(db, tid, "'ridge':* | !(regression) & \"2026\"", limit=2)
        source = await db.get(ResearchSource, sources[2].id)
        source.ingestion_status = 'FAILED'
        await db.commit()
        result = await tool.search_similar_chunks(db, tid, 'Ridge regression', limit=3)
        assert [c.id for c, _ in result] == [chunks[1].id]
        assert await tool.search_similar_chunks(db, uuid.uuid4(), 'Ridge regression') == []


@pytest.mark.asyncio
async def test_bad_vector_dimensions_do_not_poison_lexical_transaction(corpus, monkeypatch):
    from app.tools import embedder as module
    tid, _, chunks = corpus
    tool = object.__new__(EmbedderTool)
    tool.embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[1., 0., 0.]))
    tool.model_name = 'fixture'
    monkeypatch.setattr(module, 'reserve_provider_call', AsyncMock(return_value=uuid.uuid4()))
    monkeypatch.setattr(module, 'settle_provider_call', AsyncMock())
    monkeypatch.setattr(module, 'assert_task_active', AsyncMock())
    async with AsyncSessionLocal() as db:
        chunk = await db.get(DocumentChunk, chunks[1].id)
        chunk.embedding = [1., 0.]
        await db.commit()
        result = await tool.search_similar_chunks(db, tid, 'Ridge regression', 2,
                                                  {'task_id': str(tid), 'attempt_number': 1})
        assert len(result) == 2
        assert await db.scalar(text('SELECT 1')) == 1


@pytest.mark.asyncio
async def test_long_high_frequency_source_cannot_crowd_other_relevant_sources_out_of_pool(corpus):
    tid, sources, chunks = corpus
    tool = object.__new__(EmbedderTool)
    tool.embeddings = None
    async with AsyncSessionLocal() as db:
        for i in range(50):
            db.add(DocumentChunk(research_task_id=tid, source_id=sources[1].id, chunk_index=100+i,
                                 content='Ridge regression prediction ' * 20))
        await db.commit()
        result = await tool.search_similar_chunks(db, tid, 'Ridge regression prediction', limit=2)
        assert {c.source_id for c, _ in result} == {sources[1].id, sources[2].id}


@pytest.mark.asyncio
async def test_dimension_preflight_avoids_billing_and_corrupt_source_links_are_excluded(corpus):
    tid, sources, chunks = corpus
    tool = object.__new__(EmbedderTool)
    query = AsyncMock()
    tool.embeddings = SimpleNamespace(aembed_query=query)
    tool.dimension = 3
    async with AsyncSessionLocal() as db:
        chunk = await db.get(DocumentChunk, chunks[1].id)
        chunk.embedding = [1., 0.]
        own_task = await db.get(ResearchTask, tid)
        other = ResearchTask(user_id=own_task.user_id, title='Foreign research', research_question='A different task')
        db.add(other)
        await db.flush()
        foreign_source = ResearchSource(research_task_id=other.id, source_tag='foreign', url='https://example.org/foreign')
        db.add(foreign_source)
        await db.flush()
        bad = DocumentChunk(research_task_id=tid, source_id=foreign_source.id, chunk_index=0,
                            content='Ridge regression Ridge regression Ridge regression')
        db.add(bad)
        await db.commit()
        result = await tool.search_similar_chunks(db, tid, 'Ridge regression', 3,
                                                  {'task_id':str(tid), 'attempt_number':1})
        assert {c.id for c, _ in result} == {chunks[1].id, chunks[2].id}
        query.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_identity_is_not_guessed_when_papers_share_boilerplate(corpus):
    tid, _, chunks = corpus
    async with AsyncSessionLocal() as db:
        first = await db.get(DocumentChunk, chunks[0].id)
        second = await db.get(DocumentChunk, chunks[1].id)
        first.content = second.content = 'Shared quoted sentence.'
        await db.flush()
        item = {'claim':'A scoped finding', 'evidence_quote':'Shared quoted sentence.'}
        assert await persist_grounded_claims(db, tid, [item], [first, second]) == []
        accepted = await persist_grounded_claims(db, tid, [{**item, 'chunk_id': str(second.id),
            'assumptions':['Shared quoted sentence.', 'Invented theorem condition']}], [first, second])
        assert accepted[0]['source_id'] == str(second.source_id)
        assert accepted[0]['assumptions'] == ['Shared quoted sentence.']
        assert await persist_grounded_claims(db, tid, [{**item, 'chunk_id': str(uuid.uuid4())}], [first, second]) == []
        assert await persist_grounded_claims(db, uuid.uuid4(), [{**item, 'chunk_id': str(second.id)}], [second]) == []


@pytest.mark.asyncio
async def test_pdf_line_wrap_quote_is_persisted_as_its_original_literal_span(corpus):
    tid, _, chunks = corpus
    async with AsyncSessionLocal() as db:
        chunk=await db.get(DocumentChunk,chunks[1].id)
        chunk.content='The method reduced\n   prediction error in this sample.'
        await db.flush()
        item=dict(claim='A sample-specific result', evidence_quote='The method reduced prediction error in this sample.', chunk_id=str(chunk.id))
        accepted=await persist_grounded_claims(db,tid,[item],[chunk])
        assert accepted[0]['evidence_quote'] == chunk.content
        assert accepted[0]['quote_match_method'] == 'WHITESPACE_ALIGNED_TO_SOURCE'
        repeated=await persist_grounded_claims(db,tid,[{**item,'evidence_quote':chunk.content}],[chunk])
        assert repeated[0]['claim_id'] == accepted[0]['claim_id']


@pytest.mark.asyncio
async def test_same_finding_from_distinct_sources_keeps_distinct_copyable_markers(corpus, monkeypatch):
    from app.agents import nodes
    tid, _, chunks = corpus
    items = [{'claim':'Predictive results require contextual interpretation.',
              'evidence_quote':c.content, 'chunk_id':str(c.id)} for c in chunks[1:]]
    async with AsyncSessionLocal() as db:
        first = await persist_grounded_claims(db, tid, items, chunks)
        assert len({c['claim_id'] for c in first}) == 2
        repeated = await persist_grounded_claims(db, tid, items, chunks)
        assert [c['claim_id'] for c in repeated] == [c['claim_id'] for c in first]
        await db.commit()
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    markers = ''.join(f"[[@claim:{c['claim_id']}]]" for c in first)
    final = await nodes.post_processor_node({'claims':first, 'draft_report_markdown':f'# Discussion\nA contextual comparison {markers}.'})
    assert len({c['source_id'] for c in final['citations']}) == 2
    assert '[1][2]' in final['final_report_markdown']


@pytest.mark.asyncio
async def test_historical_shared_claim_is_not_rewritten_or_reused_as_ambiguous_marker(corpus):
    from app.models.grounding import ResearchClaim, Evidence, ClaimEvidence
    tid, _, chunks = corpus
    async with AsyncSessionLocal() as db:
        legacy = ResearchClaim(research_task_id=tid, claim_text='A shared finding')
        db.add(legacy)
        proofs = [Evidence(research_task_id=tid, source_id=c.source_id, chunk_id=c.id,
                           content=c.content, evidence_type='QUOTE') for c in chunks[1:]]
        db.add_all(proofs)
        await db.flush()
        db.add_all([ClaimEvidence(claim_id=legacy.id, evidence_id=e.id) for e in proofs])
        await db.flush()
        items = [{'claim':legacy.claim_text, 'chunk_id':str(c.id), 'evidence_quote':c.content} for c in chunks[1:]]
        result = await persist_grounded_claims(db, tid, items, chunks)
        assert len({c['claim_id'] for c in result}) == 2
        assert str(legacy.id) not in {c['claim_id'] for c in result}
        assert len(list(await db.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == legacy.id)))) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('research_type,findings', [
    ('REVIEW', ('Urban tree shade reduced surface temperature in the sampled streets.',
                'Urban tree cooling estimates vary with season and local street geometry.')),
    ('EMPIRICAL_COMPUTATIONAL', ('Ridge regression reduced prediction error against the mean baseline in this dataset.',
                               'Ridge regression has limitations under distribution shift; causal effects were not tested.')),
    ('EMPIRICAL_HUMAN', ('Survey respondents reported greater perceived usefulness of research assistants.',
                       'Survey self-selection limits generalization to other students.')),
])
async def test_analyst_tracks_quote_candidates_and_gaps_across_study_types(corpus, monkeypatch, research_type, findings):
    from app.agents import nodes
    from app.tools import embedder as module
    tid, _, chunks = corpus
    async with AsyncSessionLocal() as db:
        for i, finding in enumerate(findings, start=1):
            row = await db.get(DocumentChunk, chunks[i].id)
            row.content = finding
            chunks[i].content = finding
        await db.commit()
    topic = {'REVIEW':'urban tree cooling', 'EMPIRICAL_COMPUTATIONAL':'Ridge baseline prediction',
             'EMPIRICAL_HUMAN':'student perceptions of research assistants'}[research_type]
    needs = [dict(need_id='results', question=f'What comparisons concern {topic}?', search_query=topic+' comparison', section_id='results'),
             dict(need_id='limits', question=f'What limits concern {topic}?', search_query=topic+' limitations', section_id='discussion'),
             dict(need_id='causes', question=f'Is there causal evidence about {topic}?', search_query=topic+' causality', section_id='discussion')]
    class Retriever:
        async def search_similar_chunks(self, db, task_id, query, **_kwargs):
            index = 1 if query == needs[0]['question'] else 2 if query == needs[1]['question'] else None
            return [] if index is None else [(await db.get(DocumentChunk, chunks[index].id), 1.)]
    class LLM:
        def with_structured_output(self, _schema): return self
        async def ainvoke(self, messages):
            prompt = messages[0].content
            cid = re.search(r'Chunk ID: ([0-9a-f-]+)', prompt)[1]
            quote = next(c.content for c in chunks if str(c.id) == cid)
            return nodes.AnalystExtraction(claims=[nodes.ExtractedClaim(claim=quote, evidence_quote=quote, chunk_id=cid)])
    monkeypatch.setattr(module, 'EmbedderTool', Retriever)
    monkeypatch.setattr(nodes, 'get_fast_llm', lambda: LLM())
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    result = await nodes.analyst_node({'task_id': str(tid), 'research_type': research_type,
                                      'research_question':'Which effects are supported?', 'plan': {'evidence_needs': needs}})
    assert len({c['source_id'] for c in result['claims']}) == 2
    assert {c['evidence_need_id'] for c in result['claims']} == {'results', 'limits'}
    assert result['evidence_need_coverage']['missing_need_ids'] == ['causes']
    assert 'not entailment' in result['evidence_need_coverage']['scope']


@pytest.mark.asyncio
async def test_macro_loop_keeps_web_vector_cap_and_does_not_expand_provider_spend(corpus, monkeypatch):
    from app.tools import embedder as module
    tid, sources, _ = corpus
    tool = object.__new__(EmbedderTool)
    tool.model_name = 'fixture'
    async def embed(texts): return [[1., 0.] for _ in texts]
    provider = AsyncMock(side_effect=embed)
    tool.embeddings = SimpleNamespace(aembed_documents=provider)
    monkeypatch.setattr(module, 'reserve_provider_call', AsyncMock(return_value=uuid.uuid4()))
    monkeypatch.setattr(module, 'settle_provider_call', AsyncMock())
    monkeypatch.setattr(module, 'assert_task_active', AsyncMock())
    async with AsyncSessionLocal() as db:
        for i in range(20):
            db.add(DocumentChunk(research_task_id=tid, source_id=sources[0].id, chunk_index=i+1,
                                 content=f'Additional original passage {i}'))
        await db.commit()
        assert await tool.embed_existing_chunks(db, tid, sources[0].id, {'task_id':str(tid), 'attempt_number':1}) == 8
        await db.commit()
        assert await tool.embed_existing_chunks(db, tid, sources[0].id, {'task_id':str(tid), 'attempt_number':1}) == 0
    assert provider.await_count == 1
