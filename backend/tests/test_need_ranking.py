from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import uuid
import pytest

from app.services.evidence_selection import metadata_triage_order, balance_by_need


def _item_key(item):
    if isinstance(item, tuple):
        return str(item[0])
    return str(getattr(item, "full_text_url", None) or getattr(item, "url", ""))


def test_mixed_two_needs_retains_rare_candidate():
    items = [
        SimpleNamespace(url="https://site.org/1", full_text_url="https://site.org/pdf/1", title="Paper 1"),
        SimpleNamespace(url="https://site.org/2", full_text_url="https://site.org/pdf/2", title="Paper 2"),
        SimpleNamespace(url="https://site.org/3", full_text_url="https://site.org/pdf/3", title="Paper 3 (Rare)"),
    ]
    needs = [
        {"need_id": "need_common", "question": "Common Q"},
        {"need_id": "need_rare", "question": "Rare Q"},
    ]
    assessments = [
        {"candidate_id": "c01", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_common"]},
        {"candidate_id": "c02", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_common"]},
        {"candidate_id": "c03", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_rare"]},
    ]
    ordered_items, rows = metadata_triage_order(items, assessments, needs=needs)
    balanced = balance_by_need(ordered_items, needs, rows, _item_key)
    # Round-robin picks need_common (item 1), then need_rare (item 3), then remaining (item 2)
    assert [x.title for x in balanced] == ["Paper 1", "Paper 3 (Rare)", "Paper 2"]


@pytest.mark.asyncio
@pytest.mark.parametrize('rare_fetch_fails', [False, True])
async def test_researcher_preserves_need_diversity_through_fetch_and_source_cap(monkeypatch, rare_fetch_fails):
    from app.agents import nodes
    from app.tools import search, scraper
    from app.tools.search_models import SearchResult
    from app.services import provider_budget
    candidates = [SearchResult(title=title, url=f'https://example.org/{i}', query='shared discovery query',
                               content='Metadata for the controlled test.')
                  for i, title in enumerate(['common first', 'common second', 'rare first', 'rare backup'])]
    monkeypatch.setattr(search, 'execute_parallel_searches', AsyncMock(return_value=(candidates, [])))
    fetched = {str(c.url): 'Fetched original text for '+c.title for c in candidates
               if not (rare_fetch_fails and c.title == 'rare first')}
    monkeypatch.setattr(scraper, 'fetch_urls_parallel', AsyncMock(return_value=fetched))
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    monkeypatch.setattr(nodes, 'record_agent_run', AsyncMock())
    monkeypatch.setattr(nodes, 'get_fast_llm', lambda: SimpleNamespace(with_structured_output=lambda _: object()))
    monkeypatch.setattr(provider_budget, 'assert_task_active', AsyncMock())
    async def assess(_state, _model, messages, **kwargs):
        payload = json.loads(messages[0].content.split('<candidates>')[1].split('</candidates>')[0])
        assert kwargs['output_tokens'] == 4096
        return nodes.SourceTriage(assessments=[nodes.MetadataAssessment(candidate_id=c['candidate_id'],
            relevance='DIRECT', study_role='PRIMARY', reason='Provisional fixture metadata judgment',
            need_ids=['rare' if c['title'].startswith('rare') else 'common', 'invented']) for c in payload])
    invoke = AsyncMock(side_effect=assess)
    monkeypatch.setattr(nodes, 'invoke_llm_with_budget', invoke)
    result = await nodes.researcher_node({'task_id':str(uuid.uuid4()), 'attempt_number':1, 'max_sources':2,
        'enforce_provider_budget':True, 'delta_queries':['shared discovery query'], 'research_question':'Two distinct questions',
        'plan':{'evidence_needs':[{'need_id':name, 'question':name+' question', 'search_query':'shared discovery query'}
                                  for name in ['common', 'rare']]}})
    assert [s['title'] for s in result['collected_sources']] == ['common first', 'rare backup' if rare_fetch_fails else 'rare first']
    assert invoke.await_count == 1
    assert all('invented' not in d['need_ids'] for d in result['source_selection_log'][0]['candidates'])
    assert result['source_selection_log'][0]['needs_without_metadata_candidates'] == []


def test_shared_multi_need_candidate_does_not_block_the_next_need_queue():
    items = ['shared', 'popular', 'rare']
    needs = [{'need_id':'a'}, {'need_id':'b'}]
    decisions = [dict(fetch_url=key, relevance='DIRECT', need_ids=ids)
                 for key, ids in [('shared',['a','b']), ('popular',['a']), ('rare',['b'])]]
    assert balance_by_need(items, needs, decisions, lambda x:x)[:2] == ['shared', 'rare']


def test_filtered_subset_after_fetch_failure_selects_backup():
    items = [
        SimpleNamespace(url="https://site.org/1", full_text_url="https://site.org/pdf/1", title="Paper 1"),
        SimpleNamespace(url="https://site.org/2", full_text_url="https://site.org/pdf/2", title="Backup Paper 2"),
    ]
    needs = [{"need_id": "need_a", "question": "Q A"}]
    assessments = [
        {"candidate_id": "c01", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_a"]},
        {"candidate_id": "c02", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_a"]},
    ]
    ordered_items, rows = metadata_triage_order(items, assessments, needs=needs)
    # Assume item 1 failed network fetch upstream; caller re-balances with remaining surviving subset
    subset = [ordered_items[1]]
    balanced = balance_by_need(subset, needs, rows, _item_key)
    assert len(balanced) == 1
    assert balanced[0].title == "Backup Paper 2"


def test_unknown_need_ids_ignored_and_missing_or_duplicate_assessment():
    items = [
        SimpleNamespace(url="https://site.org/1", title="Item 1"),
        SimpleNamespace(url="https://site.org/2", title="Item 2"),
        SimpleNamespace(url="https://site.org/3", title="Item 3"),
    ]
    needs = [{"need_id": "valid_1", "question": "Q1"}]
    assessments = [
        # c01 has valid need and unknown need
        {"candidate_id": "c01", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["valid_1", "bogus_need", "valid_1"]},
        # Duplicate assessments for c02 makes it ambiguous -> missing/ambiguous fallback
        {"candidate_id": "c02", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["valid_1"]},
        {"candidate_id": "c02", "relevance": "CONTEXT", "study_role": "GUIDE", "need_ids": ["valid_1"]},
        # c03 is missing
    ]
    ordered_items, rows = metadata_triage_order(items, assessments, needs=needs)
    assert rows[0]["need_ids"] == ["valid_1"]
    assert rows[1]["need_ids"] == []
    assert rows[1]["metadata_assessment_present"] is False
    assert rows[2]["need_ids"] == []
    assert rows[2]["metadata_assessment_present"] is False

    balanced = balance_by_need(ordered_items, needs, rows, _item_key)
    assert len(balanced) == 3
    assert balanced[0].title == "Item 1"
    assert {b.title for b in balanced} == {"Item 1", "Item 2", "Item 3"}


def test_foundation_only_primary():
    items = [
        SimpleNamespace(url="https://site.org/1", title="Review Doc"),
        SimpleNamespace(url="https://site.org/2", title="Primary Doc"),
    ]
    needs = [{"need_id": "foundation_need", "role": "FOUNDATION", "question": "Foundational"}]
    assessments = [
        # Non-PRIMARY should have foundation need stripped
        {"candidate_id": "c01", "relevance": "DIRECT", "study_role": "REVIEW", "need_ids": ["foundation_need"]},
        {"candidate_id": "c02", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["foundation_need"]},
    ]
    ordered_items, rows = metadata_triage_order(items, assessments, needs=needs)
    assert rows[0]["need_ids"] == []
    assert rows[1]["need_ids"] == ["foundation_need"]

    balanced = balance_by_need(ordered_items, needs, rows, _item_key)
    assert balanced[0].title == "Primary Doc"
    assert balanced[1].title == "Review Doc"


def test_no_items_discarded_and_no_hints_returns_unchanged():
    items = [
        SimpleNamespace(url="https://site.org/1", title="Item 1"),
        SimpleNamespace(url="https://site.org/2", title="Item 2"),
    ]
    needs = [{"need_id": "need_1", "question": "Q1"}]
    # OUT_OF_SCOPE and CONTEXT do not retain need_ids
    assessments = [
        {"candidate_id": "c01", "relevance": "OUT_OF_SCOPE", "study_role": "UNCERTAIN", "need_ids": ["need_1"]},
        {"candidate_id": "c02", "relevance": "CONTEXT", "study_role": "UNCERTAIN", "need_ids": ["need_1"]},
    ]
    ordered_items, rows = metadata_triage_order(items, assessments, needs=needs)
    assert rows[0]["need_ids"] == []
    assert rows[1]["need_ids"] == []

    balanced = balance_by_need(ordered_items, needs, rows, _item_key)
    assert balanced == ordered_items
    assert len(balanced) == len(items)


def test_overlapping_landing_urls_disambiguated_by_fetch_url_and_tuples():
    items = [
        ("https://shared.landing.org/paper1.pdf", "Item A"),
        ("https://shared.landing.org/paper2.pdf", "Item B"),
    ]
    # Landing URL is shared, but full_text_url differs
    item_objects = [
        SimpleNamespace(url="https://shared.landing.org", full_text_url="https://shared.landing.org/paper1.pdf", title="Item A"),
        SimpleNamespace(url="https://shared.landing.org", full_text_url="https://shared.landing.org/paper2.pdf", title="Item B"),
    ]
    needs = [
        {"need_id": "need_a", "question": "QA"},
        {"need_id": "need_b", "question": "QB"},
    ]
    assessments = [
        {"candidate_id": "c01", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_a"]},
        {"candidate_id": "c02", "relevance": "DIRECT", "study_role": "PRIMARY", "need_ids": ["need_b"]},
    ]
    ordered_items, rows = metadata_triage_order(item_objects, assessments, needs=needs)
    assert rows[0]["fetch_url"] == "https://shared.landing.org/paper1.pdf"
    assert rows[1]["fetch_url"] == "https://shared.landing.org/paper2.pdf"
    assert rows[0]["url"] == "https://shared.landing.org"

    balanced_tuples = balance_by_need(items, needs, rows, _item_key)
    assert balanced_tuples == [
        ("https://shared.landing.org/paper1.pdf", "Item A"),
        ("https://shared.landing.org/paper2.pdf", "Item B"),
    ]
