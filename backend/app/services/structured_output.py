"""Keep provider response grammars small without relaxing local validation."""
from copy import deepcopy
from typing import Any

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel


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
    if model_name.startswith("gemini-") and isinstance(schema, type) and issubclass(schema, BaseModel):
        return model.with_structured_output(_gemini_wire_schema(schema.model_json_schema())) | RunnableLambda(schema.model_validate)
    return model.with_structured_output(schema)
