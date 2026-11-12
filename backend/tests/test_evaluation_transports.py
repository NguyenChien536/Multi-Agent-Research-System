"""Offline adapter contract checks: no real provider requests."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from pydantic import BaseModel, Field, ValidationError
from langchain_core.messages import AIMessage, HumanMessage
from app.evaluation.protocol import Controls
from app.evaluation.transports import GeminiTransport, OpenAITransport, build_transport, validate_transport_profile
from app.core.config import settings
from tests.test_evaluation_execution import bundle

class Result(BaseModel):
    answer: str = Field(min_length=3)

class Client:
    def __init__(self, **kwargs):
        self.kwargs=kwargs; self.copies=[]; self.schemas=[]
        self.raw=AIMessage(content='{"answer":"valid"}',usage_metadata={'input_tokens':10,'output_tokens':5,'total_tokens':15},response_metadata={'model_name':'gemini-3.5-flash-lite'})
        self.parsed={'answer':'valid'}
        self.ainvoke=AsyncMock(return_value=self.raw)
    def model_copy(self,update):
        self.copies.append(update)
        return self
    def with_structured_output(self,schema,**kwargs):
        self.schemas.append((schema,kwargs))
        return SimpleNamespace(ainvoke=AsyncMock(side_effect=lambda _: {'raw':self.raw,'parsed':self.parsed}))

@pytest.fixture
def controls():
    return Controls(provider='gemini',model='gemini-3.5-flash-lite',model_revision='unavailable',temperature=None,sampling_mode='provider_default',language='en',output_contract='REVIEW-v4',retrieval_profile='frozen-lexical-v1-1024-128',max_llm_calls=5,max_input_tokens=100000,max_output_tokens=20000,max_cost_usd=0.5,timeout_seconds=90).model_dump()

@pytest.fixture
def sdk(monkeypatch):
    import langchain_google_genai
    import langchain_openai
    created=[]
    def make(**kwargs):
        client=Client(**kwargs);created.append(client);return client
    monkeypatch.setattr(langchain_google_genai,'ChatGoogleGenerativeAI',make)
    monkeypatch.setattr(langchain_openai,'ChatOpenAI',make)
    monkeypatch.setattr(settings,'GEMINI_API_KEY','fixture-key-never-a-real-secret')
    monkeypatch.setattr(settings,'OPENAI_API_KEY','fixture-key-never-a-real-secret')
    return created

@pytest.mark.asyncio
async def test_gemini_pins_transport_and_preserves_raw_usage(controls,sdk):
    transport=build_transport(controls)
    client=sdk[0]
    assert client.kwargs['model']==controls['model'] and client.kwargs['temperature'] is None
    assert client.kwargs['vertexai'] is False and client.kwargs['thinking_level']=='low'
    assert client.kwargs['max_retries']==0 and client.kwargs['cache'] is False
    raw,parsed=await transport.request([HumanMessage(content='A controlled request')],Result,512)
    assert parsed.answer=='valid' and raw is client.raw
    assert raw.usage_metadata['input_tokens']==10
    assert client.copies==[{'max_output_tokens':512}]
    assert client.schemas[0][1]=={'include_raw':True}
    assert 'minLength' not in str(client.schemas[0][0])
    client.parsed={'answer':'x'}
    with pytest.raises(ValidationError): await transport.request([],Result,512)
    client.parsed=None
    assert (await transport.request([],Result,512))[1] is None

@pytest.mark.asyncio
async def test_plain_response_and_explicit_zero_temperature_on_supported_model(controls,sdk):
    transport=GeminiTransport({**controls,'model':'gemini-2.5-pro','sampling_mode':'temperature','temperature':0.0})
    assert sdk[0].kwargs['temperature']==0.0
    assert 'thinking_level' not in sdk[0].kwargs
    raw,parsed=await transport.request([],None,300)
    assert raw is parsed and raw is sdk[0].raw
    sdk[0].ainvoke.assert_awaited_once()

@pytest.mark.parametrize('change',[{'temperature':0.2,'sampling_mode':'temperature'},{'model':'gpt-4o'},{'model':'gemini-embedding-2'},{'model':'gemini-3.8-live'}])
def test_invalid_gemini_profile_stops_before_client_creation(controls,sdk,change):
    with pytest.raises(ValueError): GeminiTransport({**controls,**change})
    assert not sdk

@pytest.mark.parametrize('change',[{'temperature':0.2},{'sampling_mode':'temperature'}])
def test_controls_do_not_claim_configured_temperature_for_provider_default(controls,change):
    with pytest.raises(ValidationError): Controls.model_validate({**controls,**change})

@pytest.mark.asyncio
async def test_legacy_openai_transport_stays_available_and_pinned(controls,sdk):
    profile={**controls,'provider':'openai','model':'gpt-4o-mini','temperature':0.2,'sampling_mode':'temperature'}
    transport=build_transport(profile)
    assert isinstance(transport,OpenAITransport)
    await transport.request([],Result,600)
    assert sdk[0].copies==[{'max_tokens':600}]
    assert sdk[0].schemas[0][1]=={'method':'function_calling','include_raw':True}
    with pytest.raises(ValueError): build_transport({**profile,'provider':'unspecified'})


def test_verified_flash_lite_estimate_includes_standard_output_rate():
    from app.services.agent_run import estimate_cost
    assert estimate_cost('gemini-3.5-flash-lite',1000000,1000000)==2.8


def test_dry_profile_validation_does_not_construct_clients(controls,sdk):
    validate_transport_profile(controls)
    assert not sdk
    with pytest.raises(ValueError):
        validate_transport_profile({**controls,'provider':'openai'})
    with pytest.raises(ValueError):
        validate_transport_profile({**controls,'temperature':0.2,'sampling_mode':'temperature'})
    assert not sdk


def test_gemini_dry_plan_validates_rates_without_api_calls(bundle,tmp_path,capsys,sdk):
    import json
    from app.evaluation.protocol import freeze
    from app.evaluation.execute import main
    source=tmp_path/'inputs'/'spec.json'
    spec=json.loads(source.read_text())
    spec['controls'].update(provider='gemini',model='gemini-3.5-flash-lite',sampling_mode='provider_default',temperature=None)
    source.write_text(json.dumps(spec))
    frozen=tmp_path/'gemini-bundle'
    freeze(source,frozen)
    args=[str(frozen),'--case','smoke-1','--arm','multi_agent','--campaign-cap','2','--input-rate','0.30','--output-rate','2.50']
    assert main(args)==0
    output=json.loads(capsys.readouterr().out)
    assert output['provider_calls']==0 and output['controls']['temperature'] is None
    assert not sdk and not (frozen/'campaign').exists()
    args[-1]='0.6'
    assert main(args)==2
    assert 'verified' in capsys.readouterr().err
    assert not sdk and not (frozen/'campaign').exists()

