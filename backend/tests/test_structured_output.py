import json

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.agents.nodes import CriticVerdict
from app.services.structured_output import compatible_structured_output
from pydantic import create_model


class StructuredClient:
    def __init__(self, response):
        self.response = response
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return RunnableLambda(lambda _: self.response)


@pytest.mark.asyncio
async def test_gemini_uses_small_wire_schema_and_returns_validated_pydantic_output():
    original = CriticVerdict.model_json_schema()
    client = StructuredClient({"verdict": "REVISE", "evidence_reviews": [{
        "statement_id": "p1", "judgment": "UNSUPPORTED", "reason": "No supplied evidence."}]})
    result = await compatible_structured_output("gemini-fixture", client, CriticVerdict).ainvoke("fixture")
    wire = json.dumps(client.schema)
    assert all(f'"{key}"' not in wire for key in ("maxItems", "maxLength", "minLength", "default"))
    assert isinstance(result, CriticVerdict)
    assert result.evidence_reviews[0].supporting_claim_ids == []
    assert not result.evidence_reviews[0].assumptions_preserved
    assert CriticVerdict.model_json_schema() == original


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {"verdict": "PASS", "evidence_reviews": [{"statement_id": "p", "judgment": "SUPPORTED", "reason": "x"}] * 33},
    {"verdict": "PASS", "evidence_reviews": [{"statement_id": "p", "judgment": "SUPPORTED", "reason": "x", "supporting_claim_ids": ["c"] * 25}]},
    {"verdict": "PASS", "evidence_reviews": [{"statement_id": "p", "judgment": "SUPPORTED", "reason": ""}]},
    {"verdict": "PASS", "evidence_reviews": [{"statement_id": "p", "judgment": "INVENTED", "reason": "x"}]},
])
async def test_simplified_transport_still_rejects_invalid_reviewer_output(invalid):
    client = StructuredClient(invalid)
    with pytest.raises(ValidationError):
        await compatible_structured_output("gemini-fixture", client, CriticVerdict).ainvoke("fixture")


def test_other_provider_keeps_native_schema():
    client = StructuredClient({"verdict": "PASS"})
    compatible_structured_output("other-fixture", client, CriticVerdict)
    assert client.schema is CriticVerdict


def test_schema_keyword_names_are_preserved_when_they_are_domain_fields():
    schema = create_model("DomainFields", default=(str, ...), maxLength=(str, ...))
    client = StructuredClient({"default": "a", "maxLength": "b"})
    compatible_structured_output("gemini-fixture", client, schema)
    assert set(client.schema["properties"]) == {"default", "maxLength"}
