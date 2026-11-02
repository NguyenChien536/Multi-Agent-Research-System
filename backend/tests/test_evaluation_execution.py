"""Fixture-provider software checks only; these are NOT scientific evaluations."""
import asyncio
import json
import re
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import engine
from app.core.runtime import current_runtime, workflow_runtime
from app.evaluation.__main__ import initialize
from app.evaluation.corpus import FrozenCorpus, RETRIEVAL_PROFILE, chunks
from app.evaluation.execute import main, attest_revision, code_fingerprint
from app.evaluation.execution_budget import Campaign, Meter, PinnedLLM
from app.evaluation.executor import execute_slot, isolated_database_url, ControllerStep
from app.evaluation.protocol import checked, digest, freeze, protocol, run_key
from app.models import User, ResearchTask, ResearchSource, DocumentChunk, ClaimEvidence, Evidence, ResearchClaim, AgentRun
from app.services.provider_budget import ProviderBudgetExceeded
from tests.manuscript_helpers import complete_manuscript, supported_critic_response


@pytest.fixture
def bundle(tmp_path):
    inputs = tmp_path / "inputs"
    initialize(inputs)
    path = inputs / "spec.json"
    spec = json.loads(path.read_text())
    spec["controls"].update(model="fixture-pinned", retrieval_profile=RETRIEVAL_PROFILE)
    # A planted answer/rubric marker must never reach any provider prompt.
    spec["cases"][0]["expected_points"][0]["description"] = "SECRET_RUBRIC_NOT_FOR_AGENTS"
    path.write_text(json.dumps(spec), encoding="utf-8")
    root = tmp_path / "bundle"
    freeze(path, root)
    return root


class FixtureTransport:
    def __init__(self, *, fail=False, delay=0, revision="unavailable", first_verdict="PASS", usage=True):
        self.prompts, self.schemas = [], []
        self.fail, self.delay, self.revision = fail, delay, revision
        self.first_verdict, self.critics, self.controllers, self.usage = first_verdict, 0, 0, usage

    async def request(self, messages, schema, outputs):
        prompt = messages[0].content
        assert "SECRET_RUBRIC_NOT_FOR_AGENTS" not in prompt
        self.prompts.append(prompt)
        self.schemas.append(schema.__name__ if schema else "manuscript")
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("fixture provider failure with SECRET_KEY_MUST_NOT_LEAK")
        from app.agents.nodes import SupervisorPlan, AnalystExtraction, CriticVerdict
        claim = dict(claim="The fictional scores were 2 and 3.", evidence_quote="scores 2 and 3")
        if schema is SupervisorPlan:
            parsed = schema(research_angle="Controlled synthetic fixture", search_queries=["fictional scores"], required_sections=[])
        elif schema is AnalystExtraction:
            parsed = schema(claims=[claim])
        elif schema is CriticVerdict:
            parsed = supported_critic_response(messages)
            if self.critics == 0:
                parsed.verdict = self.first_verdict
                parsed.missing_areas = ["additional fictional observations"] if self.first_verdict == "NEED_MORE_DATA" else []
            self.critics += 1
        elif schema is ControllerStep:
            self.controllers += 1
            parsed = schema(action="RETRIEVE", query="fictional scores") if self.controllers == 1 else schema(
                action="WRITE", claims=[claim], manuscript=complete_manuscript(
                    "The fictional scores were 2 and 3 [[evidence:0]].", language="en", prompt=prompt))
        elif schema is None:
            markers = list(dict.fromkeys(re.findall(r"\[\[@claim:[^\]]+\]\]", prompt)))
            parsed = AIMessage(content=complete_manuscript(
                "The fictional scores were 2 and 3 " + " ".join(markers) + ".", language="en", prompt=prompt))
        else:
            raise AssertionError(f"Unexpected schema {schema}")
        raw = AIMessage(content="fixture", usage_metadata={"input_tokens": 100, "output_tokens": 100, "total_tokens": 200} if self.usage else None,
                        response_metadata={"model_name": self.revision, "finish_reason": "stop"})
        return raw, parsed


async def slot(root, arm="multi_agent", attempt=1, transport=None, ceiling=2.0):
    frozen = protocol(root)
    transport = transport or FixtureTransport()
    with Campaign(root / "campaign", digest(frozen), ceiling, 0.15, 0.6) as campaign:
        result = await execute_slot(root, "smoke-1", arm, attempt,
            sessions=async_sessionmaker(engine, expire_on_commit=False), client=transport, campaign=campaign)
    record = checked(root / "runs" / f"{run_key('smoke-1', arm, attempt)}.json")
    return result, record, transport


async def cleanup(record):
    import uuid
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        task = await db.get(ResearchTask, uuid.UUID(record["trace"]["evaluation_task_id"]))
        if task:
            owner = await db.get(User, task.user_id)
            await db.delete(owner)
            await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("arm", ["single_agent", "multi_agent", "no_macro_loop"])
async def test_actual_nodes_execute_on_frozen_sources_with_real_lineage(bundle, arm, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Evaluation attempted to use a default DB or a live source/embedding provider")
    from app.core import database
    from app.tools.search import TavilySearchTool
    from app.tools.scraper import ScraperTool
    monkeypatch.setattr(database, "_default_sessions", forbidden)
    monkeypatch.setattr(TavilySearchTool, "__init__", forbidden)
    monkeypatch.setattr(ScraperTool, "__init__", forbidden)
    result, record, transport = await slot(bundle, arm)
    try:
        assert result["status"] in {"COMPLETED", "NEEDS_REVIEW"}
        assert record["eligible"] and record["report"]
        assert record["used_source_ids"] == ["alpha"]
        assert record["network_calls"] == 0
        assert current_runtime() is None
        assert record["trace"]["claims"]
        assert "SECRET_KEY_MUST_NOT_LEAK" not in json.dumps(record)
        if arm == "single_agent":
            assert set(transport.schemas) == {"ControllerStep"}
            assert record["status"] == "NEEDS_REVIEW"
        else:
            assert {"SupervisorPlan", "AnalystExtraction", "CriticVerdict", "manuscript"} <= set(transport.schemas)
        roles = [e["role"] for e in record["trace"]["events"] if e["event"] == "role"]
        assert "CURATOR" in roles and "POST_PROCESSOR" in roles
        assert len(transport.prompts) == record["llm_calls"]
        assert record["input_tokens"] == record["llm_calls"] * 100
        import uuid
        task_id = uuid.UUID(record["trace"]["evaluation_task_id"])
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            claims = (await db.scalars(select(ResearchClaim).where(ResearchClaim.research_task_id == task_id))).all()
            assert claims
            links = (await db.execute(select(Evidence, DocumentChunk, ResearchSource)
                .join(DocumentChunk, Evidence.chunk_id == DocumentChunk.id)
                .join(ResearchSource, Evidence.source_id == ResearchSource.id)
                .where(Evidence.research_task_id == task_id))).all()
            assert links and all(e.content in c.content and c.source_id == s.id for e, c, s in links)
            assert all(s.text_scope == "WEB_PAGE" for _, _, s in links)
            histories = (await db.scalars(select(AgentRun).where(AgentRun.research_task_id == task_id))).all()
            assert histories and all(h.input_tokens == 0 and float(h.estimated_cost) == 0 for h in histories)
    finally:
        await cleanup(record)


@pytest.mark.asyncio
async def test_macro_ablation_preserves_micro_configuration(bundle):
    _, b, _ = await slot(bundle, "multi_agent", transport=FixtureTransport(first_verdict="NEED_MORE_DATA"))
    _, c, _ = await slot(bundle, "no_macro_loop", transport=FixtureTransport(first_verdict="NEED_MORE_DATA"))
    try:
        roles_b = [e["role"] for e in b["trace"]["events"] if e["event"] == "role" and e["iteration"] is None]
        roles_c = [e["role"] for e in c["trace"]["events"] if e["event"] == "role" and e["iteration"] is None]
        assert roles_b.count("RESEARCHER") == 2
        assert roles_c.count("RESEARCHER") == 1
        assert b["micro_revision_enabled"] and c["micro_revision_enabled"]
    finally:
        await cleanup(b)
        await cleanup(c)


@pytest.mark.asyncio
async def test_failure_keeps_attempt_and_conservative_cost_and_allows_rerun(bundle):
    result, record, _ = await slot(bundle, transport=FixtureTransport(fail=True))
    try:
        assert result["status"] == "FAILED" and not record["eligible"]
        assert record["llm_calls"] == 1 and record["estimated_cost_usd"] > 0
        assert record["error"] == "RuntimeError"
        assert "SECRET_KEY_MUST_NOT_LEAK" not in json.dumps(record)
        with pytest.raises(FileExistsError):
            await slot(bundle)
        _, rerun, _ = await slot(bundle, attempt=2)
        try:
            assert checked(bundle / "runs" / f"{run_key('smoke-1', 'multi_agent', 1)}.json")["status"] == "FAILED"
        finally:
            await cleanup(rerun)
    finally:
        await cleanup(record)


@pytest.mark.asyncio
async def test_campaign_refuses_request_before_provider_and_remembers_cost(bundle):
    result, record, transport = await slot(bundle, ceiling=0.000001)
    try:
        assert result["status"] == "BUDGET_EXCEEDED"
        assert not transport.prompts and record["llm_calls"] == 0
    finally:
        await cleanup(record)
    with pytest.raises(ValueError, match="cannot be changed"):
        await slot(bundle, attempt=2, ceiling=2.0)
    assert not (bundle / "campaign" / "campaign.lock").exists()


@pytest.mark.asyncio
async def test_budget_limited_draft_is_retained_as_needs_review(bundle):
    # Re-freeze a different legitimate smoke protocol before any run.
    p = checked(bundle / "protocol.json")
    p["controls"]["max_llm_calls"] = 3
    from app.evaluation.protocol import encoded
    (bundle / "protocol.json").write_bytes(encoded({"sha256": digest(p), "payload": p}))
    _, record, _ = await slot(bundle)
    try:
        assert record["status"] == "NEEDS_REVIEW"
        assert record["report"] and record["llm_calls"] == 3
        assert record["trace"]["critic_review_metadata"]["budget_limited"]
    finally:
        await cleanup(record)


@pytest.mark.asyncio
async def test_timeout_retains_unknown_provider_charge(bundle):
    p = checked(bundle / "protocol.json")
    p["controls"]["timeout_seconds"] = 1
    from app.evaluation.protocol import encoded
    (bundle / "protocol.json").write_bytes(encoded({"sha256": digest(p), "payload": p}))
    _, record, _ = await slot(bundle, transport=FixtureTransport(delay=2))
    try:
        assert record["status"] == "TIMEOUT" and record["estimated_cost_usd"] > 0
        assert current_runtime() is None
    finally:
        await cleanup(record)


def test_local_corpus_retrieval_and_chunking_are_pinned(bundle):
    source = "a" * 2100
    parts = list(chunks(source))
    assert [len(p) for p in parts] == [1024, 1024, 308]
    p = protocol(bundle)
    c = FrozenCorpus(p["sources"], ["alpha"], [])
    with pytest.raises(ValueError, match="outside"):
        asyncio.run(c.fetch(["https://example.com/not-frozen"]))


@pytest.mark.parametrize("url", ["postgresql+asyncpg://a:b@localhost/research_db",
    "postgresql+asyncpg://a:b@localhost/eval_prod", "sqlite:///eval_test.db"])
def test_live_or_unsupported_database_is_rejected(url):
    with pytest.raises(ValueError):
        isolated_database_url(url, "postgresql+asyncpg://a:b@different-host/eval_prod")


def test_explicit_test_database_can_be_selected():
    assert isolated_database_url("postgresql+asyncpg://a:b@localhost/research_eval_run",
        "postgresql+asyncpg://a:b@localhost/research_db").database == "research_eval_run"


def test_plan_requires_no_key_database_or_paid_calls(bundle, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EVALUATION_DATABASE_URL", raising=False)
    args = [str(bundle), "--case", "smoke-1", "--arm", "multi_agent",
            "--campaign-cap", "1", "--input-rate", "0.15", "--output-rate", "0.6"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["provider_calls"] == 0
    assert not (bundle / "campaign").exists()
    assert main(args + ["--execute"]) == 2  # Never spend real calls on smoke fixtures.


def test_code_attestation_rejects_changed_sources(bundle):
    with pytest.raises(ValueError, match="fingerprint"):
        attest_revision(protocol(bundle))
    assert re.fullmatch(r"[0-9a-f]{64}", code_fingerprint())


@pytest.mark.asyncio
async def test_budget_serializes_parallel_reservations_and_retains_unknown_usage(bundle):
    frozen = protocol(bundle)
    controls = {**frozen["controls"], "max_llm_calls": 1}
    with Campaign(bundle / "campaign", digest(frozen), 2.0, 0.15, 0.6) as campaign:
        meter = Meter(controls, campaign, "test", [])
        llm = PinnedLLM(FixtureTransport(fail=True), meter)
        result = await asyncio.gather(*[meter.invoke(llm, [HumanMessage(content="fixture")]) for _ in range(3)], return_exceptions=True)
        assert sum(isinstance(r, ProviderBudgetExceeded) for r in result) == 2
        assert meter.calls == 1 and meter.cost > 0
    with Campaign(bundle / "campaign", digest(frozen), 2.0, 0.15, 0.6) as reopened:
        assert reopened.state["charged_usd"] == meter.cost


@pytest.mark.asyncio
async def test_runtime_is_task_local_and_resets_after_errors():
    a, b = SimpleNamespace(model_name="a"), SimpleNamespace(model_name="b")
    async def check(value):
        try:
            with workflow_runtime(value):
                await asyncio.sleep(0.01)
                assert current_runtime() is value
                raise RuntimeError("fixture")
        except RuntimeError:
            assert current_runtime() is None
    await asyncio.gather(check(a), check(b))


@pytest.mark.asyncio
@pytest.mark.parametrize("arm", ["multi_agent", "no_macro_loop"])
async def test_micro_revision_remains_enabled_in_both_multi_agent_arms(bundle, arm):
    _, record, _ = await slot(bundle, arm, transport=FixtureTransport(first_verdict="REVISE"))
    try:
        roles = [e["role"] for e in record["trace"]["events"] if e["event"] == "role"]
        assert roles.count("WRITER") == 2
        assert record["micro_revision_enabled"]
    finally:
        await cleanup(record)


@pytest.mark.asyncio
async def test_missing_usage_keeps_full_reservation_instead_of_zero_cost(bundle):
    _, record, _ = await slot(bundle, "single_agent", transport=FixtureTransport(usage=False))
    try:
        attempts = [e for e in record["trace"]["events"] if e["event"] == "provider_attempt"]
        assert all(not e["usage_measured"] for e in attempts)
        assert record["estimated_cost_usd"] > 0
        assert record["output_tokens"] == sum(e["reserved_output_tokens"] for e in attempts)
    finally:
        await cleanup(record)


def test_campaign_lock_refuses_concurrent_processes_and_preserves_owner_lock(bundle):
    p = digest(protocol(bundle))
    with Campaign(bundle / "campaign", p, 1.0, 0.15, 0.6):
        with pytest.raises(FileExistsError):
            with Campaign(bundle / "campaign", p, 1.0, 0.15, 0.6):
                pytest.fail("Second campaign owner was admitted")
        assert (bundle / "campaign" / "campaign.lock").exists()
    assert not (bundle / "campaign" / "campaign.lock").exists()


@pytest.mark.asyncio
async def test_measured_revision_mismatch_is_retained_but_ineligible(bundle):
    p = checked(bundle / "protocol.json")
    p["controls"]["model_revision"] = "fixture-revision-1"
    from app.evaluation.protocol import encoded
    (bundle / "protocol.json").write_bytes(encoded({"sha256": digest(p), "payload": p}))
    _, record, _ = await slot(bundle, "single_agent", transport=FixtureTransport(revision="fixture-revision-2"))
    try:
        assert record["report"] and not record["eligible"]
        assert record["reported_control_violations"]
        assert record["observed_controls"]["model_revision"] == "fixture-revision-2"
    finally:
        await cleanup(record)


@pytest.mark.asyncio
async def test_database_claim_rejects_existing_user_data():
    from app.evaluation.executor import claim_database
    import uuid
    uid = uuid.uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(User(id=uid, username=f"ordinary-{uid.hex[:10]}", email=f"{uid}@example.com", password_hash="fixture"))
        await db.commit()
    try:
        with pytest.raises(ValueError, match="containing users"):
            await claim_database(engine, "a" * 64)
    finally:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await db.delete(await db.get(User, uid))
            await db.commit()


def test_openai_adapter_disables_cache_and_retries_and_keeps_usage(monkeypatch):
    from app.evaluation.execute import OpenAITransport
    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "fixture-not-a-real-key")
    import langchain_openai
    calls = []
    raw = AIMessage(content="fixture", usage_metadata={"input_tokens": 4, "output_tokens": 3, "total_tokens": 7})
    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def model_copy(self, *, update):
            calls.append(update)
            return self
        def with_structured_output(self, schema, **kwargs):
            calls.append(kwargs)
            return self
        async def ainvoke(self, messages):
            return {"raw": raw, "parsed": ControllerStep(action="RETRIEVE", query="fixture")}
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", Client)
    transport = OpenAITransport({"model": "fixture-model", "temperature": 0.2, "timeout_seconds": 10})
    returned, _ = asyncio.run(transport.request([HumanMessage(content="fixture")], ControllerStep, 200))
    assert calls[0]["cache"] is False and calls[0]["max_retries"] == 0
    assert calls[1] == {"max_tokens": 200}
    assert calls[2]["include_raw"] is True
    assert returned.usage_metadata["input_tokens"] == 4


@pytest.mark.asyncio
async def test_real_openai_sdk_adapter_with_local_http_fixture_keeps_raw_usage(monkeypatch):
    """Exercise the actual SDK and structured parser; HTTP stays in memory."""
    import httpx
    from app.evaluation.execute import OpenAITransport
    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "fixture-not-a-real-key")
    observed = []
    def respond(request):
        body = json.loads(request.content)
        observed.append(body)
        assert body["model"] == "gpt-4o-mini"
        assert body.get("max_completion_tokens", body.get("max_tokens")) == 123
        return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 1,
            "model": "fixture-provider-revision", "choices": [{"index": 0, "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call_fixture",
                    "type": "function", "function": {"name": "ControllerStep", "arguments": json.dumps({"action": "RETRIEVE", "query": "fixture"})}}]}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        from langchain_openai import ChatOpenAI
        transport = OpenAITransport({"model": "gpt-4o-mini", "temperature": 0.2, "timeout_seconds": 10})
        transport.client = ChatOpenAI(model="gpt-4o-mini", api_key="fixture-not-a-real-key",
            http_async_client=http_client, max_retries=0, cache=False, temperature=0.2)
        raw, parsed = await transport.request([HumanMessage(content="fixture")], ControllerStep, 123)
    assert len(observed) == 1 and parsed.action == "RETRIEVE"
    assert raw.usage_metadata["input_tokens"] == 4
    assert raw.response_metadata["model_name"] == "fixture-provider-revision"


@pytest.mark.asyncio
async def test_campaign_cost_persists_between_failed_attempts(bundle):
    _, first, _ = await slot(bundle, ceiling=0.004, transport=FixtureTransport(fail=True))
    try:
        assert first["llm_calls"] == 1 and first["status"] == "FAILED"
        _, second, transport = await slot(bundle, attempt=2, ceiling=0.004, transport=FixtureTransport(fail=True))
        try:
            assert second["status"] == "BUDGET_EXCEEDED"
            assert not transport.prompts and second["llm_calls"] == 0
        finally:
            await cleanup(second)
    finally:
        await cleanup(first)


@pytest.mark.asyncio
async def test_parallel_analyst_is_drained_before_failed_run_finalization(bundle):
    from app.agents.nodes import AnalystExtraction, SupervisorPlan
    p = checked(bundle / "protocol.json")
    p["controls"]["max_llm_calls"] = 2  # Supervisor + first of two concurrent analyst calls.
    from app.evaluation.protocol import encoded
    (bundle / "protocol.json").write_bytes(encoded({"sha256": digest(p), "payload": p}))
    class TwoQueries(FixtureTransport):
        completed = False
        async def request(self, messages, schema, outputs):
            if schema is AnalystExtraction:
                await asyncio.sleep(0.1)
                self.completed = True
            raw, parsed = await super().request(messages, schema, outputs)
            if schema is SupervisorPlan:
                parsed.search_queries = ["fictional scores", "additional fictional scores"]
            return raw, parsed
    transport = TwoQueries()
    _, record, _ = await slot(bundle, transport=transport)
    try:
        assert record["status"] == "BUDGET_EXCEEDED" and transport.completed
        events = record["trace"]["events"]
        assert events[-1]["event"] == "stop"
        assert all(e["state"] != "STARTED" for e in events if e["event"] == "provider_attempt")
    finally:
        await cleanup(record)
