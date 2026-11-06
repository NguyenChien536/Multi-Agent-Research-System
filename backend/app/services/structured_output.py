"""Keep provider response grammars small without relaxing local validation."""
from copy import deepcopy
from typing import Any

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel
from app.prompts import render_prompt


class StructuredOutputFailure(ValueError):
    """A completed provider response failed local validation; never expose its body."""

    def __init__(self, code, response):
        super().__init__(code)
        self.response = response


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
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
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
            if text.startswith('```json\n') and text.endswith('```'):
                text = text[8:-3].strip()
            try:
                validated = schema.model_validate(json.loads(text))
            except ValueError:
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
        return RunnableLambda(add_schema) | model.bind(extra_body=body) | RunnableLambda(validate_json)
    if model_name.startswith("gemini-") and isinstance(schema, type) and issubclass(schema, BaseModel):
        return model.with_structured_output(_gemini_wire_schema(schema.model_json_schema())) | RunnableLambda(schema.model_validate)
    return model.with_structured_output(schema)
