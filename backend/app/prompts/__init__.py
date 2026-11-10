"""Load non-executable prompt templates, independently of agent orchestration."""
from pathlib import Path
import re


_ROOT = Path(__file__).resolve().parent / 'templates'
_NAME = re.compile(r'[a-z][a-z0-9_]{0,63}')
_VARIABLE = re.compile(r'\{\{\s*([a-z][a-z0-9_]*)\s*\}\}')


class PromptTemplateError(ValueError):
    """A template is missing or its named context does not match the contract."""


def render_prompt(name: str, **context) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise PromptTemplateError('Invalid prompt template name')
    path = (_ROOT / (name + '.txt')).resolve()
    if path.parent != _ROOT.resolve():
        raise PromptTemplateError('Prompt template must remain inside its asset directory')
    try:
        template = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise PromptTemplateError(f'Cannot read prompt template: {name}') from exc
    remainder = _VARIABLE.sub('', template)
    if not template.strip() or '{{' in remainder or '}}' in remainder:
        raise PromptTemplateError(f'Empty or malformed prompt template: {name}')
    required = set(_VARIABLE.findall(template))
    missing = required.difference(context)
    extra = set(context).difference(required)
    if missing or extra:
        raise PromptTemplateError(
            f'Prompt context mismatch for {name}; missing={sorted(missing)}, extra={sorted(extra)}'
        )
    # One substitution pass: source text containing template markers is data,
    # never evaluated as Python/Jinja or processed as another template.
    return _VARIABLE.sub(lambda match: str(context[match.group(1)]), template)
