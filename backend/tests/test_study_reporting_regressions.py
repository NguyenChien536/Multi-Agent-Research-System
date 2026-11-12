import math
from unittest.mock import AsyncMock

import pytest

from app.services.fieldwork_intake import validate_fieldwork_result, frozen_csv_statistics
from app.services.fieldwork_reporting import numeric_table_mismatches
from app.services.manuscript import editorial_instructions, manuscript_contract, manuscript_provenance
from app.services.scientific_paper import scientific_context, validate_scientific_reporting
from app.services.study_protocol import normalize_protocol_markdown, protocol_constraints


def survey():
    text = 'id,usefulness,effort\n' + ''.join(f'{i+1},{2+i%4},{1+(i*3)%5}\n' for i in range(24))
    return validate_fieldwork_result('test.csv', text.encode())


def test_csv_statistics_count_actual_rows_and_distinguish_sd_definitions():
    summary = survey()['csv_descriptive_statistics']
    assert summary['rows_count'] == 24
    values = summary['columns']['effort']
    assert values['value_counts'] == {'1.0': 5, '2.0': 5, '3.0': 4, '4.0': 5, '5.0': 5}
    assert sum(values['value_counts'].values()) == 24
    assert values['mean'] == 3
    assert values['sample_sd'] > values['population_sd']
    assert summary['columns']['usefulness']['sample_sd'] == pytest.approx(math.sqrt(30/23))


def test_csv_statistics_preserve_missing_data_and_skip_text_or_nonfinite_columns():
    evidence = validate_fieldwork_result('test.csv', b'x,label,bad\n1,a,nan\n,b,2\n3,c,inf\n')
    columns = evidence['csv_descriptive_statistics']['columns']
    assert set(columns) == {'x'}
    assert columns['x']['count'] == 2 and columns['x']['missing_count'] == 1
    assert columns['x']['mean'] == 2
    assert validate_fieldwork_result('test.txt', b'A qualitative observation')['csv_descriptive_statistics'] is None


def test_old_csv_snapshot_is_rechecked_only_when_complete_and_hash_matching():
    evidence = survey()
    expected = evidence.pop('csv_descriptive_statistics')
    assert frozen_csv_statistics(evidence) == expected
    assert 'csv_descriptive_statistics' not in evidence
    assert frozen_csv_statistics({**evidence, 'text_excerpt': 'changed'}) is None
    assert frozen_csv_statistics({**evidence, 'excerpt_truncated': True}) is None


def test_numeric_table_guard_reproduces_wrong_sd_and_impossible_frequency_total():
    summary = survey()['csv_descriptive_statistics']
    text = '| Variable | Mean | Standard deviation (SD) | Response distribution |\n|---|---|---|---|\n| `usefulness` | 3.50 | 1.13 | 2:6, 3:6, 4:6, 5:6 |\n| `effort` | 3.00 | 1.41 | 1:5, 2:5, 3:5, 4:5, 5:5 |'
    findings = numeric_table_mismatches(text, summary)
    assert any('usefulness' in f and 'sample_sd' in f for f in findings)
    assert any('effort' in f and 'frequencies' in f for f in findings)
    context = scientific_context({'user_data_submission': {'artifact_evidence': survey()}})
    gate = validate_scientific_reporting(text, manuscript_contract('EMPIRICAL_HUMAN', 'en'), context, [])
    assert 'FIELDWORK_NUMERIC_MISMATCH' in {f['code'] for f in gate}


def test_numeric_table_guard_accepts_rounding_and_explicit_population_sd():
    summary = survey()['csv_descriptive_statistics']
    text = '| Variable | Mean | Sample SD | Response distribution |\n|---|---|---|---|\n| usefulness | 3.50 | 1.14 | 2:6, 3:6, 4:6, 5:6 |'
    assert numeric_table_mismatches(text, summary) == []
    assert numeric_table_mismatches(text.replace('Sample SD', 'Population SD').replace('1.14', '1.12'), summary) == []
    assert numeric_table_mismatches(text.replace('3.50', '1e999999999'), summary)


def test_protocol_transport_repair_preserves_math_code_and_real_multiline_text():
    bad = r'# Study\n\n## Method\nUse $\nu$ and `C:\new`; inspect the data.'
    fixed = normalize_protocol_markdown(bad)
    assert '\n\n## Method\nUse' in fixed
    assert r'$\nu$' in fixed and r'`C:\new`' in fixed
    assert normalize_protocol_markdown('# Study\n\nA literal `\\n` example.') == '# Study\n\nA literal `\\n` example.'


def test_protocol_guidance_restricts_executable_work_and_allows_descriptive_questions():
    assert 'SAME frozen' in protocol_constraints('EMPIRICAL_COMPUTATIONAL')
    assert 'does not execute cross-validation' in protocol_constraints('EMPIRICAL_COMPUTATIONAL')
    assert 'hypotheses may be an empty list' in protocol_constraints('EMPIRICAL_HUMAN')
    assert 'not a promised automated step' in protocol_constraints('EMPIRICAL_HUMAN')


def test_review_scope_depends_on_grounded_sources_not_collected_record_count():
    provenance = manuscript_provenance({'collected_sources': [{}] * 8,
        'claims': [{'source_id': 'one', 'evidence_id': 'e1', 'claim_id': 'c1'}]})
    assert provenance['available_source_count'] == 8 and provenance['grounded_source_count'] == 1
    assert 'Only 1 distinct source' in editorial_instructions(manuscript_contract('REVIEW', 'en'), provenance)
    text = editorial_instructions(manuscript_contract('EMPIRICAL_COMPUTATIONAL', 'en'), {'grounded_source_count': 0})
    assert 'literature-backed comparison or field-level gap cannot be established' in text


def test_publication_retains_standard_regression_math_without_enabling_tex_input():
    import io
    import zipfile
    from app.services.publication_export import _inline, build_publication_bundle
    math_text = r'$\hat{y}=\bar{y}+\boldsymbol{\beta}^{T}\mathbf{x},\quad x\in\mathbb{R}$'
    supported = math_text
    assert _inline(supported, {}) == supported
    assert r'\input{/etc/passwd}' not in _inline(r'$\input{/etc/passwd}$', {})
    display = '$$\n' + r'\hat{y}=\bar{y}+\boldsymbol{\beta}^{T}\mathbf{x}' + '\n$$'
    raw, _ = build_publication_bundle('Study', '# Study\n\n## Methods\n\n' + display, {}, [], 'IEEE_CONFERENCE', version_id='v1', version_number=1)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        tex = archive.read('main.tex').decode()
    assert display in tex
    assert 'amssymb' in tex


def test_search_retries_do_not_credit_collection_to_failures_or_multiply_counts():
    from app.services.research_quality import attribute_collection_counts
    activity = [{'provider': 'Crossref', 'query': 'q', 'status': status}
                for status in ['FAILED', 'SUCCESS', 'SUCCESS']]
    rows = attribute_collection_counts(activity, 'now', accepted_count={('Crossref', 'q'): 2})
    assert [row['accepted_count'] for row in rows] == [0, 0, 2]
    assert sum(row['accepted_count'] for row in rows) == 2
    assert 'accepted_count' not in activity[0]


def test_delta_mae_is_not_compared_to_absolute_model_mae():
    contract = manuscript_contract('EMPIRICAL_COMPUTATIONAL', 'en')
    context = {'analysis': {'status': 'COMPLETED', 'metrics': {'model': {'mae': 1.335145}, 'baseline': {'mae': 12.338741}}}}
    text = '## Results\n\nRidge regression error yields a Delta MAE of -11.003596. The baseline yielded an MAE of 12.338741.'
    assert not any(f['code'] == 'METRIC_MISMATCH' for f in validate_scientific_reporting(text, contract, context, []))
    wrong = text + '\n\nRidge MAE = 55.0.'
    assert any(f['code'] == 'METRIC_MISMATCH' for f in validate_scientific_reporting(wrong, contract, context, []))


@pytest.mark.asyncio
async def test_descriptive_protocol_without_hypotheses_resumes_without_provider(monkeypatch):
    from app.agents import nodes
    monkeypatch.setattr(nodes, '_record_progress', AsyncMock())
    forbidden = AsyncMock(side_effect=AssertionError('Must reuse a complete descriptive protocol'))
    monkeypatch.setattr(nodes, 'invoke_llm_with_budget', forbidden)
    protocol = {'research_questions': ['What do the observations describe?'], 'hypotheses': [],
                'protocol_markdown': '# Descriptive protocol\n\nUse descriptive summaries.'}
    result = await nodes.methodologist_node({'protocol': protocol, 'research_type': 'EMPIRICAL_HUMAN'})
    assert result['protocol'] == protocol and result['status'] == 'WAITING_USER_DATA'
    forbidden.assert_not_awaited()
