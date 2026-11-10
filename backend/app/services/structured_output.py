"""Keep provider response grammars small without relaxing local validation."""
from copy import deepcopy
from typing import Any

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel
from app.prompts import render_prompt
import re
import logging

logger = logging.getLogger(__name__)


def compact_prompt_schema(value):
    """Remove display-only metadata; never remove domain keys or constraints."""
    if isinstance(value, list):
        return [compact_prompt_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {key: ({name: compact_prompt_schema(child) for name, child in item.items()}
                  if key in {'properties', '$defs', 'definitions'} else compact_prompt_schema(item))
            for key, item in value.items() if key not in {'title', 'examples'}}


class StructuredOutputFailure(ValueError):
    """A completed provider response failed local validation; never expose its body."""

    def __init__(self, code, response):
        super().__init__(code)
        self.response = response


def strict_wire_schema(schema):
    """Constrain object keys at transport; keep original Pydantic validation."""
    if isinstance(schema, list):
        return [strict_wire_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {key: ({name: strict_wire_schema(child) for name, child in value.items()}
                    if key in {'properties', '$defs', 'definitions'} else strict_wire_schema(value))
              for key, value in schema.items() if key != 'default'}
    if result.get('type') == 'object' and 'properties' in result:
        result['required'] = list(result['properties'])
        result['additionalProperties'] = False
    return result


def supports_strict_schema(schema):
    """Arbitrary-key dictionaries cannot be closed without losing domain data."""
    if isinstance(schema, list):
        return all(supports_strict_schema(item) for item in schema)
    if not isinstance(schema, dict):
        return True
    if schema.get('type') == 'object' and 'properties' not in schema and schema.get('additionalProperties') is not False:
        return False
    return all(supports_strict_schema(value) for value in schema.values())


def _gemini_wire_schema(schema: dict) -> dict:
    # Gemini rejected the bounded Critic schema with INVALID_ARGUMENT but accepted
    # this simpler wire schema in a controlled integration pilot. Defaults and
    # length/cardinality constraints remain enforced by Pydantic after parsing.
    omitted = {"minItems", "maxItems", "minLength", "maxLength", "default"}

    def simplify(value):
        if isinstance(value, dict):
            return {key: ({name: simplify(definition) for name, definition in item.items()}
                          if key in {"properties", "$defs", "definitions"} else simplify(item))
                    for key, item in value.items() if key not in omitted}
        if isinstance(value, list):
            return [simplify(item) for item in value]
        return value

    return simplify(deepcopy(schema))


def compatible_structured_output(model_name: str, model: Any, schema: Any):
    """Native JSON output, followed by the original schema's full validation."""
    if model_name.startswith("byok:") and isinstance(schema, type) and issubclass(schema, BaseModel):
        import json
        from langchain_core.messages import SystemMessage
        schema_text = json.dumps(compact_prompt_schema(schema.model_json_schema()), ensure_ascii=False, separators=(',', ':'))
        def add_schema(messages):
            instruction = render_prompt('structured_output', json_schema=schema_text)
            return [SystemMessage(content=instruction), *messages]
        def validate_json(response):
            if str((getattr(response, 'response_metadata', None) or {}).get('finish_reason', '')).lower() == 'length':
                raise StructuredOutputFailure('MODEL_OUTPUT_TRUNCATED: JSON response reached its output limit', response)
            content = getattr(response, 'content', None)
            if not isinstance(content, str) or not content.strip():
                raise StructuredOutputFailure('MODEL_INVALID_JSON: Provider returned no JSON text', response)
            text = content.strip()
            fence = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n?```', text, re.I)
            if fence:
                text = fence[1].strip()
            try:
                validated = schema.model_validate(json.loads(text))
            except ValueError as exc:
                fields = {'root:json_syntax'}
                if callable(getattr(exc, 'errors', None)):
                    fields = set()
                    for error in exc.errors(include_input=False, include_context=False, include_url=False)[:8]:
                        first = (error.get('loc') or ('root',))[0]
                        name = first if first in schema.model_fields else 'root'
                        fields.add(str(name) + ':' + str(error.get('type', 'invalid')))
                logger.warning('Structured validation rejected schema=%s fields=%s', schema.__name__, sorted(fields))
                raise StructuredOutputFailure('MODEL_INVALID_JSON: Model returned invalid structured data.', response) from None
            # Pydantic serialization stays unchanged, while budget accounting
            # retains provider-reported usage (including reasoning tokens).
            object.__setattr__(validated, 'usage_metadata', getattr(response, 'usage_metadata', None))
            object.__setattr__(validated, 'response_metadata', getattr(response, 'response_metadata', None))
            return validated
        # Send the same JSON-mode request through the standard completion
        # transport. SDK beta .parse assumes native-provider response details;
        # custom gateways need local, strict JSON/Pydantic validation instead.
        body = {**(getattr(model, 'extra_body', None) or {}), 'response_format': {'type': 'json_object'}}
        from app.services.model_connection import current_connection
        connection = current_connection()
        if connection and connection.structured_output_mode == 'prompt_json':
            body.pop('response_format', None)
        if connection and connection.structured_output_mode == 'json_schema' and supports_strict_schema(schema.model_json_schema()):
            wire = strict_wire_schema(schema.model_json_schema())
            if getattr(connection, 'base_url', '') == 'https://generativelanguage.googleapis.com/v1beta/openai':
                wire = _gemini_wire_schema(wire)
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': schema.__name__[:64], 'strict': True,
                'schema': wire,
            }}
        return RunnableLambda(add_schema) | model.bind(extra_body=body) | RunnableLambda(validate_json)
    if model_name.startswith("gemini-") and isinstance(schema, type) and issubclass(schema, BaseModel):
        return model.with_structured_output(_gemini_wire_schema(schema.model_json_schema())) | RunnableLambda(schema.model_validate)
    return model.with_structured_output(schema)
