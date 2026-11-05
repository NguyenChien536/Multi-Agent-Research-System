from pathlib import Path
import re

import pytest

from app import prompts


@pytest.mark.parametrize('name', [
    'supervisor', 'source_triage', 'evidence_analyst', 'methodologist', 'writer',
    'critic', 'critic_evidence_support', 'report_question_answering', 'structured_output',
])
def test_prompt_assets_render_with_explicit_context_and_keep_data_literal(name):
    template = (Path(prompts.__file__).parent / 'templates' / (name + '.txt')).read_text(encoding='utf-8')
    fields = set(re.findall(r'\{\{\s*([a-z][a-z0-9_]*)\s*\}\}', template))
    value = 'Dữ liệu {{ not_an_instruction }} \\frac{a}{b}\n{"source": "evidence"}'
    rendered = prompts.render_prompt(name, **{field: value for field in fields})
    assert rendered.strip()
    if fields:
        assert value in rendered
    for field in fields:
        assert '{{ ' + field + ' }}' not in rendered


@pytest.mark.parametrize('name', ['../core/config', '/etc/passwd', 'writer.txt', 'a/b', 'a\\b', ''])
def test_prompt_names_cannot_read_arbitrary_paths(name):
    with pytest.raises(prompts.PromptTemplateError):
        prompts.render_prompt(name)


def test_missing_and_unexpected_context_fail_without_echoing_values():
    secret_data = 'private context must not appear in the exception'
    with pytest.raises(prompts.PromptTemplateError) as missing:
        prompts.render_prompt('writer', research_question=secret_data)
    assert secret_data not in str(missing.value)
    with pytest.raises(prompts.PromptTemplateError):
        prompts.render_prompt('report_question_answering', accidental_parameter=secret_data)


def test_edits_are_read_on_the_next_call_without_a_stale_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, '_ROOT', tmp_path)
    path = tmp_path / 'sample.txt'
    path.write_text('First instruction: {{ context }}', encoding='utf-8')
    assert prompts.render_prompt('sample', context='data') == 'First instruction: data'
    path.write_text('Revised instruction: {{ context }}', encoding='utf-8')
    assert prompts.render_prompt('sample', context='data') == 'Revised instruction: data'


@pytest.mark.parametrize('content', ['', '  ', '{{ user.__class__ }}', '{{ missing-close', '{{ for item }}'])
def test_empty_or_executable_template_syntax_is_rejected(tmp_path, monkeypatch, content):
    monkeypatch.setattr(prompts, '_ROOT', tmp_path)
    (tmp_path / 'invalid.txt').write_text(content, encoding='utf-8')
    with pytest.raises(prompts.PromptTemplateError):
        prompts.render_prompt('invalid')


def test_unknown_prompt_fails_instead_of_sending_empty_instructions():
    with pytest.raises(prompts.PromptTemplateError):
        prompts.render_prompt('not_a_registered_asset')
