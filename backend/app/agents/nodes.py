import asyncio
import contextvars
import logging
import hashlib
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import ResearchState
from app.prompts import render_prompt
from app.core.config import settings
from app.core.runtime import current_runtime
from app.services.manuscript import (
    attach_manuscript_contract, editorial_instructions,
    manuscript_provenance, validate_manuscript, normalize_claim_markers, writer_claim_context,
)
from app.services.scientific_paper import (
    scientific_context, build_scientific_figures, figure_instructions,
    materialize_figures, validate_scientific_reporting, measured_comparison_table, insert_measured_comparison_table,
)
from app.services.academic_writing import writing_guidance, writing_limits, manuscript_skeleton
from app.services.research_quality import unique_quote_claims, canonicalize_quote_markers, inject_search_ledger, query_coverage, bounded_quality_batches, LEDGER_HEADINGS
from app.services.evidence_review import prepare_evidence_review, evaluate_evidence_reviews, audit_matches_draft
from app.agents.agent_schemas import (
    ArgumentSection, EvidenceNeed, MetadataAssessment, SourceTriage, SupervisorPlan,
    CriticVerdict, ExtractedClaim, AnalystExtraction, StudyPlanFields,
    ProtocolVariableGroup, MethodologistPlan, MethodologistProtocol,
)
from app.services.structured_output import compatible_structured_output
from app.services.references import format_reference, reference_identity, reference_suffixes, reference_metadata_notes
from app.services.agent_run import (
    estimate_cost,
    extract_tokens,
    get_active_model_name,
    record_agent_run,
)
from app.services.provider_budget import (
    DEFAULT_CALL_OUTPUT_TOKENS,
    ProviderBudgetExceeded,
    ResearchTaskStopped,
    estimate_tokens,
    reserve_provider_call,
    settle_provider_call,
)

from app.agents.writing_runtime import WritingRoleServices
from app.agents.writing_support import (
    _report_sections, _review_batches, _claim_lineage_findings,
    format_language_instruction, format_section_outline_prompt,
)
from app.agents.writer import run_writer
from app.agents.critic import run_critic

logger = logging.getLogger(__name__)


async def _record_progress(state: ResearchState, step: str, iteration: int | None = None) -> None:
    if runtime := current_runtime():
        runtime.progress(step, iteration)
    from app.services.progress import record_agent_progress

    updated = await record_agent_progress(
        state.get("task_id"),
        state.get("attempt_number"),
        step,
        iteration,
    )
    if state.get("enforce_provider_budget") and not updated:
        raise ResearchTaskStopped("Research task was cancelled or this worker attempt is stale")

# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------
from langchain_core.globals import set_llm_cache
from redis import Redis as _Redis
try:
    from langchain_community.cache import RedisCache  # type: ignore[import]
except ModuleNotFoundError as exc:
    if exc.name != "langchain_community":
        raise
    RedisCache = None  # type: ignore[assignment,misc]

if RedisCache is not None:
    try:
        _redis_client = _Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=3)
        set_llm_cache(RedisCache(redis_=_redis_client))
        logger.info("LLM Redis cache enabled")
    except Exception as exc:
        logger.warning("Could not connect to Redis for the LLM cache: %s", exc)
else:
    logger.warning("langchain_community is not installed; LLM Redis cache is disabled")
# 1. TIERED LLM CONFIGURATION (Theo Kiến trúc Tối ưu Hiệu năng)
# ---------------------------------------------------------------------------

# Mô hình nhỏ siêu tốc cho logic, trích xuất (Supervisor, Analyst, Critic)
_BUDGET_CALL_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "provider_budget_call_context", default=None
)


class BudgetedFallbackLLM:
    """Try configured providers in order, reserving budget for every attempt."""

    def __init__(self, models: list[tuple[str, Any]], *, pace_requests: bool = False, structured_schema: Any = None, output_limits=None, request_clients=None):
        self.models = models
        self.pace_requests = pace_requests
        self.structured_schema = structured_schema
        self.output_limits = output_limits or {}
        self.request_clients = request_clients if request_clients is not None else dict(models)

    def with_structured_output(self, schema: Any):
        return BudgetedFallbackLLM(
            [(model_name, compatible_structured_output(model_name, model, schema)) for model_name, model in self.models],
            pace_requests=self.pace_requests,
            structured_schema=schema,
            output_limits={name: getattr(model, 'max_tokens', None) or getattr(model, 'max_output_tokens', None)
                           for name, model in self.models},
            request_clients=self.request_clients,
        )

    async def ainvoke(self, messages: Any, **kwargs: Any):
        context = _BUDGET_CALL_CONTEXT.get()
        last_error: Exception | None = None
        # One bounded second pass for temporary upstream 502/503/504 failures.
        # Each attempt still passes pacing, cancellation and the durable budget.
        # Authentication/quota/invalid-output errors never trigger this pass.
        for index, (model_name, model) in enumerate(self.models * 2):
            retry_hint = ''
            expanded_output = None
            if index >= len(self.models):
                from app.services.public_errors import is_transient_provider_error
                from app.services.structured_output import StructuredOutputFailure
                repairable = self.structured_schema is not None and isinstance(last_error, StructuredOutputFailure) and str(last_error).startswith('MODEL_INVALID_JSON:')
                if context and model_name.startswith('byok:') and self.structured_schema is not None and isinstance(last_error, StructuredOutputFailure) and str(last_error).startswith('MODEL_OUTPUT_TRUNCATED:'):
                    from app.services.model_connection import current_connection
                    connection = current_connection()
                    if connection and connection.output_token_limit > context['output_tokens']:
                        expanded_output = min(connection.output_token_limit, context['output_tokens'] * 2)
                if not is_transient_provider_error(last_error) and not repairable and expanded_output is None:
                    break
                if repairable or expanded_output is not None:
                    retry_hint = render_prompt('structured_output_retry')
                    if repairable:
                        from app.services.model_connection import route_json_retry
                        route_json_retry(self.request_clients[model_name], getattr(last_error, 'response', None))
                else:
                    await asyncio.sleep(2)
            reservation_id = None
            if self.pace_requests:
                from app.services.provider_pacing import wait_for_gemini_slot, ProviderQueueTimeout
                try:
                    await wait_for_gemini_slot(model_name)
                except ProviderQueueTimeout as exc:
                    last_error = exc
                    continue  # No call/reservation; try the next configured model's own gate.
            extra_tokens = 0
            if context and self.structured_schema is not None:
                import json
                try:
                    if hasattr(self.structured_schema, "model_json_schema"):
                        schema_str = json.dumps(self.structured_schema.model_json_schema(), ensure_ascii=False)
                    else:
                        schema_str = str(self.structured_schema)
                    extra_tokens = estimate_tokens("Return one JSON object matching this schema exactly:\n" + schema_str)
                except Exception:
                    pass
            if context:
                call_output = expanded_output or context["output_tokens"]
                if model_name.startswith('byok:'):
                    from app.services.provider_budget import personal_output_capacity
                    call_output = await personal_output_capacity(context['task_id'], call_output)
                    # Structured pipelines bind this same task-scoped client.
                    # Change the real request as well as its reservation; a
                    # reservation-only clamp would leave an unbounded request.
                    client = self.request_clients[model_name]
                    if isinstance(getattr(client, 'max_tokens', None), int):
                        client.max_tokens = call_output
                    elif isinstance(getattr(client, 'max_output_tokens', None), int):
                        client.max_output_tokens = call_output
                reservation_id = await reserve_provider_call(
                    task_id=context["task_id"],
                    attempt_number=context["attempt_number"],
                    kind="llm",
                    model=model_name,
                    input_tokens=context["input_tokens"] + extra_tokens + (estimate_tokens(retry_hint) if retry_hint else 0),
                    output_tokens=call_output,
                )
            try:
                if context:
                    from app.services.provider_budget import assert_task_active
                    await assert_task_active(context["task_id"], context["attempt_number"])
                async with asyncio.timeout(settings.PROVIDER_CALL_TIMEOUT_SECONDS):
                    from langsmith import tracing_context
                    with tracing_context(enabled=False if model_name.startswith("byok:") else None):
                        attempt_messages = [*messages, HumanMessage(content=retry_hint)] if retry_hint and isinstance(messages, list) else messages
                        response = await model.ainvoke(attempt_messages, **kwargs)
                from app.services.model_connection import remember_response_model
                remember_response_model(response)
                if reservation_id:
                    prompt_text = context["prompt_text"]
                    output_text = response.model_dump_json() if hasattr(response, "model_dump_json") else str(
                        getattr(response, "content", response)
                    )
                    input_tokens, output_tokens = extract_tokens(response, prompt_text, output_text)
                    # Provider usage already includes the schema. Add its estimate
                    # only when structured parsing discarded usage metadata.
                    if not getattr(response, "usage_metadata", None) and not getattr(response, "response_metadata", None):
                        input_tokens += extra_tokens
                    await settle_provider_call(
                        task_id=context["task_id"],
                        reservation_id=reservation_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=estimate_cost(model_name, input_tokens, output_tokens),
                        succeeded=True,
                    )
                return response
            except (ProviderBudgetExceeded, ResearchTaskStopped):
                raise
            except Exception as exc:
                last_error = exc
                if reservation_id:
                    from app.services.public_errors import provider_request_rejected
                    from app.services.structured_output import StructuredOutputFailure
                    measured = isinstance(exc, StructuredOutputFailure) and (
                        getattr(exc.response, 'usage_metadata', None) or
                        (getattr(exc.response, 'response_metadata', None) or {}).get('token_usage'))
                    used_in, used_out = extract_tokens(exc.response) if measured else (0, 0)
                    await settle_provider_call(
                        task_id=context["task_id"],
                        reservation_id=reservation_id,
                        input_tokens=used_in,
                        output_tokens=used_out,
                        cost_usd=estimate_cost(model_name, used_in, used_out) if measured else 0,
                        succeeded=False,
                        rejected=provider_request_rejected(exc),
                        usage_reported=bool(measured),
                    )
                if self.pace_requests:
                    from app.services.provider_pacing import record_gemini_rate_limit
                    await record_gemini_rate_limit(model_name, exc)
                from app.services.public_errors import public_error
                logger.warning("LLM provider attempt failed (%s): %s; trying the next configured provider", model_name, public_error(str(exc)))
        if last_error:
            from app.services.public_errors import provider_failure_message, ProviderRequestRejected
            # Keep typed transport failures before falling back to text matching.
            # In particular, a generic SDK message mentioning "quota" is not 429.
            if message := provider_failure_message(last_error):
                from app.services.provider_recovery import rate_limit_error
                if limited := rate_limit_error(last_error):
                    raise limited from None
                raise ProviderRequestRejected(message) from None
            from app.services.provider_recovery import rate_limit_error
            if limited := rate_limit_error(last_error):
                raise limited from None
            from app.services.structured_output import StructuredOutputFailure
            if isinstance(last_error, StructuredOutputFailure):
                raise last_error
            from httpx import TimeoutException
            from openai import APITimeoutError
            from app.services.public_errors import ProviderResponseTimeout
            if isinstance(last_error, (TimeoutError, TimeoutException, APITimeoutError)):
                raise ProviderResponseTimeout('PROVIDER_TIMEOUT: Provider response timed out.') from None
            from app.services.public_errors import ProviderUnavailable, ProviderRequestRejected, is_transient_provider_error, provider_request_rejected
            if is_transient_provider_error(last_error):
                raise ProviderUnavailable('PROVIDER_UNAVAILABLE: Provider temporarily overloaded (503); bounded retries exhausted.') from None
            if any(name.startswith("byok:") for name, _ in self.models):
                err_str = str(last_error).lower()
                failure_type = ProviderRequestRejected if provider_request_rejected(last_error) else RuntimeError
                if "lengthfinishreason" in type(last_error).__name__.lower() or 'model_output_truncated' in err_str:
                    raise RuntimeError("MODEL_OUTPUT_TRUNCATED: The model reached its output token limit before completing JSON. This is not an API-key authentication error. Retry with sufficient output capacity.") from None
                if "429" in err_str or "rate limit" in err_str or "quota" in err_str or "credit" in err_str:
                    raise failure_type("Your API connection reached its rate limit or quota (HTTP 429). Wait and check your provider's free allowance before retrying.") from None
                if "401" in err_str or "unauthorized" in err_str or "invalid api key" in err_str or "authentication" in err_str:
                    raise failure_type("Your API key was rejected by the provider (HTTP 401). Please verify your API key.") from None
                if "404" in err_str or "not found" in err_str:
                    raise failure_type("The model was not found on this provider (HTTP 404). Please verify your model name.") from None
                if "outputparser" in last_error.__class__.__name__.lower() or "validation" in err_str or "json" in err_str:
                    raise RuntimeError("The model failed to produce valid structured JSON output for this workflow step. Please check if this model supports structured output.") from None
                if isinstance(last_error, (TimeoutError, asyncio.TimeoutError)) or "timeout" in err_str:
                    raise RuntimeError("The API connection timed out. The provider endpoint may be unreachable or responding too slowly.") from None
                raise RuntimeError(f"Your API connection failed ({last_error.__class__.__name__}). Check its key, model, quota and supported output format.") from None
            if provider_request_rejected(last_error):
                from app.services.public_errors import public_error
                raise ProviderRequestRejected(public_error(str(last_error))) from None
            raise last_error
        raise RuntimeError("No LLM provider is configured")


def _provider_model_names(provider: str, is_smart: bool) -> list[str]:
    names = {
        "gemini": ["gemini-3.5-flash", "gemini-3.5-flash-lite"] if is_smart else [
            "gemini-3.5-flash-lite", "gemini-3.5-flash"
        ],
        "openai": ["gpt-4o", "gpt-4o-mini"] if is_smart else ["gpt-4o-mini", "gpt-4o"],
        "anthropic": ["claude-3-5-sonnet-20240620", "claude-3-5-haiku-20241022"] if is_smart else [
            "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20240620"
        ],
        "groq": ["llama-3.1-8b-instant"],
    }
    return names[provider]


def build_llm_chain(is_smart: bool = False):
    if runtime := current_runtime():
        return runtime.llm
    from app.services.model_connection import current_connection, build_connection_client
    if connection := current_connection():
        models = []
        for model_name in [connection.model, *connection.fallback_models]:
            # Keep every user-selected backup as a budgeted candidate. Provider-side
            # routing alone cannot recover from a successful HTTP response that is
            # truncated or fails local structured-output validation.
            # Give each candidate its own client list; dataclasses.replace is
            # shallow by default and would otherwise share/clear the task list.
            candidate = replace(connection, model=model_name, fallback_models=[], _clients=[])
            client = build_connection_client(candidate)
            # The active task scope owns all clients and closes them together.
            connection.register_client(client)
            models.append((candidate.model_tag, client))
        return BudgetedFallbackLLM(models)
    providers = [p.strip().lower() for p in settings.LLM_PROVIDER_PRIORITY.split(",")]
    models: list[tuple[str, Any]] = []
    
    for provider in providers:
        if provider == "gemini" and getattr(settings, "GEMINI_API_KEY", None) and "your_" not in settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            for model_name in _provider_model_names(provider, is_smart):
                models.append((model_name, ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=None,
                    google_api_key=settings.GEMINI_API_KEY,
                    max_output_tokens=4096,
                    thinking_level="low",
                    max_retries=0,
                )))
        elif provider == "openai" and getattr(settings, "OPENAI_API_KEY", None) and "your_" not in settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            model_name = _provider_model_names(provider, is_smart)[0]
            models.append((model_name, ChatOpenAI(
                model=model_name,
                temperature=0.7 if is_smart else 0.2,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=4096,
                max_retries=0,
            )))
        elif provider == "anthropic" and getattr(settings, "ANTHROPIC_API_KEY", None) and "your_" not in settings.ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            model_name = _provider_model_names(provider, is_smart)[0]
            models.append((model_name, ChatAnthropic(
                model=model_name,
                temperature=0.7 if is_smart else 0.2,
                api_key=settings.ANTHROPIC_API_KEY,
                max_tokens=4096,
                max_retries=0,
            )))
        elif provider == "groq" and getattr(settings, "GROQ_API_KEY", None) and "your_" not in settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            model_name = _provider_model_names(provider, is_smart)[0]
            models.append((model_name, ChatGroq(
                model=model_name,
                temperature=0.7 if is_smart else 0.2,
                api_key=settings.GROQ_API_KEY,
                max_tokens=4096,
                max_retries=0,
            )))
            
    if not models:
        raise ValueError("Cần cấu hình ít nhất 1 API KEY hợp lệ trong LLM_PROVIDER_PRIORITY")
        
    return BudgetedFallbackLLM(models, pace_requests=True)


async def invoke_llm_with_budget(
    state: ResearchState,
    llm: Any,
    messages: Any,
    *,
    model_name: str,
    output_tokens: int = DEFAULT_CALL_OUTPUT_TOKENS,
):
    """Invoke an LLM and charge its pre-call reservation, including test doubles."""
    if runtime := current_runtime():
        return await runtime.invoke(llm, messages, output_tokens=output_tokens)
    if not state.get("enforce_provider_budget") or not state.get("task_id"):
        return await llm.ainvoke(messages)

    prompt_text = "\n".join(str(getattr(message, "content", message)) for message in messages)
    context = {
        "task_id": state["task_id"],
        "attempt_number": state.get("attempt_number", 1),
        "input_tokens": estimate_tokens(prompt_text),
        "output_tokens": output_tokens,
        "prompt_text": prompt_text,
    }
    if isinstance(llm, BudgetedFallbackLLM):
        saved_work = None
        result_key = None
        if llm.structured_schema is not None:
            from app.services.completed_work import CompletedWork
            saved_work = CompletedWork.for_state(state)
            if saved_work:
                operation = 'json:' + llm.structured_schema.__name__[:70]
                result_key = saved_work.fingerprint({'messages': [
                    {'role': getattr(message, 'type', 'text'), 'content': getattr(message, 'content', str(message))}
                    for message in messages], 'schema': llm.structured_schema.model_json_schema(),
                    'limits': llm.output_limits})
                cached = await saved_work.load(operation, result_key)
                if cached:
                    result = llm.structured_schema.model_validate(cached['value'])
                    from app.services.model_connection import current_connection
                    if cached.get('response_model') and (connection := current_connection()):
                        from types import SimpleNamespace
                        from app.services.model_connection import remember_response_model
                        remember_response_model(SimpleNamespace(response_metadata={'model_name': cached['response_model']}))
                    object.__setattr__(result, '_reused_provider_result', True)
                    logger.info('Reused completed unit task=%s operation=%s', state['task_id'], operation)
                    return result
        if any(name.startswith("byok:") for name, _ in llm.models):
            from app.services.model_connection import current_connection
            connection = current_connection()
            # Use the limit actually sent by this node, rather than reserving
            # the full manuscript allowance for every short JSON response.
            limits = [llm.output_limits.get(name) or getattr(model, 'max_tokens', None)
                      for name, model in llm.models]
            numeric_limits = [limit for limit in limits if isinstance(limit, int) and not isinstance(limit, bool)]
            selected_ceiling = max(numeric_limits) if numeric_limits else (
                connection.output_token_limit if connection else 8192)
            if connection:
                # A previous group's request mutates the reusable HTTP client.
                # Its last allocation is not the owner's model-capacity ceiling.
                selected_ceiling = connection.output_token_limit
            # A model maximum is a ceiling, not the size to allocate to every
            # short JSON/group request. Preserve capacity for the rest of the
            # paper, including conservative accounting after a timeout.
            context["output_tokens"] = min(selected_ceiling, max(output_tokens, 1024))
        token = _BUDGET_CALL_CONTEXT.set(context)
        try:
            response = await llm.ainvoke(messages)
            if saved_work and result_key:
                from app.services.model_connection import current_connection
                connection = current_connection()
                await saved_work.save(operation, result_key, {'value': response.model_dump(),
                    'response_model': getattr(connection, 'last_response_model', None)})
            return response
        finally:
            _BUDGET_CALL_CONTEXT.reset(token)

    reservation_id = await reserve_provider_call(
        task_id=context["task_id"],
        attempt_number=context["attempt_number"],
        kind="llm",
        model=model_name,
        input_tokens=context["input_tokens"],
        output_tokens=output_tokens,
    )
    try:
        from app.services.provider_budget import assert_task_active
        await assert_task_active(context["task_id"], context["attempt_number"])
        response = await llm.ainvoke(messages)
        output_text = response.model_dump_json() if hasattr(response, "model_dump_json") else str(
            getattr(response, "content", response)
        )
        input_used, output_used = extract_tokens(response, prompt_text, output_text)
        await settle_provider_call(
            task_id=context["task_id"],
            reservation_id=reservation_id,
            input_tokens=input_used,
            output_tokens=output_used,
            cost_usd=estimate_cost(model_name, input_used, output_used),
            succeeded=True,
        )
        return response
    except Exception:
        await settle_provider_call(
            task_id=context["task_id"], reservation_id=reservation_id,
            input_tokens=0, output_tokens=0, cost_usd=0, succeeded=False,
        )
        raise

def get_fast_llm():
    return build_llm_chain(is_smart=False)

def get_smart_llm():
    return build_llm_chain(is_smart=True)

# ---------------------------------------------------------------------------
# 2. SCHEMAS (Pydantic v2) CHO CÁC AGENT
# ---------------------------------------------------------------------------

async def supervisor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Supervisor Agent: Đóng vai trò lập kế hoạch và định hướng ban đầu.
    """
    await _record_progress(state, "SUPERVISOR")
    start_ts = time.monotonic()
    # Nếu kế hoạch đã được người dùng phê duyệt trước đó, tái sử dụng trực tiếp mà không cần gọi lại LLM
    if state.get("plan_approved") and state.get("plan"):
        logger.info("Task %s: Reusing approved plan without re-planning.", state.get("task_id"))
        approved_plan = attach_manuscript_contract(state["plan"], state.get("research_type", "REVIEW"), state.get("language", "en"))
        search_queries = approved_plan.get("search_queries", [])
        return {
            "current_agent": "supervisor",
            "plan": approved_plan,
            "delta_queries": search_queries,
            "current_queries": search_queries,
        }

    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    llm = get_fast_llm().with_structured_output(SupervisorPlan)

    research_type = state.get("research_type", "REVIEW")
    feedback_section = ""
    if state.get("plan_feedback"):
        feedback_section = f"\n    Lưu ý/Góp ý điều chỉnh từ người dùng: {state.get('plan_feedback')}\n"

    prompt = render_prompt('supervisor',
        research_question=state.get('research_question'),
        research_type=research_type,
        research_depth=state.get('research_depth'),
        output_language=format_language_instruction(state.get('language')),
        feedback_section=feedback_section,
    )

    try:
        # Thực thi LLM gọi schema
        plan: SupervisorPlan = await invoke_llm_with_budget(
            state, llm, [HumanMessage(content=prompt)], model_name=model_name, output_tokens=4096
        )
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(plan, prompt_str=prompt, output_str=plan.model_dump_json())
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Supervisor",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"research_question": state.get("research_question"), "depth": state.get("research_depth")},
            output_summary={"queries_count": len(plan.search_queries), "sections_count": len(plan.required_sections)},
            tool_calls=[],
        )

        # Cập nhật State
        return {
            "current_agent": "supervisor",
            "plan": attach_manuscript_contract(plan.model_dump(), research_type, state.get("language", "en")),
            "plan_version": int(state.get("plan_version", 0)) + 1,
            "delta_queries": plan.search_queries,
            "current_queries": plan.search_queries
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Supervisor",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def researcher_node(state: ResearchState) -> Dict[str, Any]:
    """
    Researcher Agent: Sử dụng Tavily API để tìm kiếm và cào web song song.
    """
    await _record_progress(state, "RESEARCHER")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    from app.tools.search import execute_parallel_searches
    from app.tools.scraper import fetch_urls_parallel
    from app.services.research_quality import balance_by_query

    queries = state.get("delta_queries", [])
    if not queries:
        return {"current_agent": "researcher"}

    try:
        remaining_sources = max(0, state.get("max_sources", 10) - len(state.get("collected_sources", [])))
        if not remaining_sources:
            return {"current_agent": "researcher", "current_iteration": state.get("current_iteration", 0) + 1}
        # 1. Gọi Tavily search (parallel)
        budget_context = None
        if state.get("enforce_provider_budget"):
            budget_context = {
                "task_id": state["task_id"],
                "attempt_number": state.get("attempt_number", 1),
            }
        if budget_context:
            search_response = await execute_parallel_searches(
                queries, max_results_per_query=5, budget_context=budget_context,
                include_activity=True, search_depth="advanced" if state.get("research_depth") == "DEEP" else settings.TAVILY_SEARCH_DEPTH,
            )
        else:
            search_response = await execute_parallel_searches(
                queries, max_results_per_query=5, include_activity=True,
                search_depth="advanced" if state.get("research_depth") == "DEEP" else settings.TAVILY_SEARCH_DEPTH,
            )
        if isinstance(search_response, tuple):
            search_results, provider_activity = search_response
        else:  # Compatible with test doubles and legacy adapters.
            search_results = search_response
            provider_activity = []

        # Bỏ qua các URL đã thu thập trước đó (Seen URL Cache)
        visited = state.get("visited_urls", set())
        new_urls_map = {}
        seen_counts: dict[tuple[str, str | None], int] = {}
        for res in search_results:
            url_str = str(res.full_text_url or res.url)
            doi_key = f"doi:{res.doi.casefold().removeprefix('https://doi.org/')}" if res.doi else None
            if url_str in visited or (doi_key and doi_key in visited):
                key = (res.provider or "web", res.query)
                seen_counts[key] = seen_counts.get(key, 0) + 1
            elif url_str not in new_urls_map:
                new_urls_map[url_str] = res

        # 2. Cào nội dung (Scraping) song song
        # Bound network fan-out even when several indexes return many candidates.
        from app.services.evidence_selection import rank_discovery_candidates, metadata_triage_order, balance_by_need, analysis_needs, MAX_TRIAGE_CANDIDATES
        ranked_results = balance_by_query(rank_discovery_candidates(list(new_urls_map.values())), queries,
                                         lambda r: r.matched_queries or [r.query])
        selection_log = []
        needs = analysis_needs(state)
        decisions = []
        need_hints = {}
        if ranked_results and (state.get("plan") or {}).get("evidence_needs") and state.get("enforce_provider_budget"):
            import json
            pool = ranked_results[:MAX_TRIAGE_CANDIDATES]
            candidates = [{"candidate_id": f"c{i+1:02d}", "title": r.title[:400],
                           "abstract_or_snippet": (r.content or "")[:600], "doi": r.doi,
                           "source_type": r.source_type, "venue": r.venue,
                           "discovery_queries": (r.matched_queries or [r.query])[:5]} for i, r in enumerate(pool)]
            triage_prompt = render_prompt('source_triage',
                research_question=str(state.get('research_question') or '')[:1500],
                evidence_needs=needs,
                candidates_json=json.dumps(candidates, ensure_ascii=False),
            )
            try:
                triage = await invoke_llm_with_budget(state, get_fast_llm().with_structured_output(SourceTriage),
                    [HumanMessage(content=triage_prompt)], model_name=get_active_model_name(is_smart=False), output_tokens=4096)
                ordered, decisions = metadata_triage_order(pool, [a.model_dump() for a in triage.assessments], needs)
                need_hints = {d["fetch_url"]: d["need_ids"] for d in decisions if d["need_ids"]}
                ranked_results = ordered + ranked_results[len(pool):]
                ranked_results = (balance_by_need(ranked_results, needs, decisions, lambda r: str(r.full_text_url or r.url))
                                  if need_hints else balance_by_query(ranked_results, queries, lambda r: r.matched_queries or [r.query]))
                hinted_ids = {need_id for ids in need_hints.values() for need_id in ids}
                selection_log = [{"version": 2, "status": "ASSESSED" if all(d["metadata_assessment_present"] for d in decisions) else "PARTIAL", "candidates": decisions,
                                  "needs_without_metadata_candidates": [n["need_id"] for n in needs if n["need_id"] not in hinted_ids],
                                  "scope": "provisional title/abstract relevance; not full-text screening or study-quality certification"}]
            except (ProviderBudgetExceeded, ResearchTaskStopped):
                raise
            except Exception as exc:
                logger.warning("Metadata triage unavailable; retaining bounded discovery ranking (%s)", type(exc).__name__)
                selection_log = [{"version": 1, "status": "UNAVAILABLE", "error_type": type(exc).__name__,
                                  "scope": "metadata assessment unavailable; discovery ranking only"}]
        ranked_urls = [str(r.full_text_url or r.url) for r in ranked_results]
        urls_to_scrape = ranked_urls[:max(5, remaining_sources * 2)]
        if budget_context:
            from app.services.provider_budget import assert_task_active
            await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])
        scraped_data = await fetch_urls_parallel(urls_to_scrape, max_concurrent=5)

        # 3. Gom kết quả vào state
        new_sources = []
        base_idx = len(state.get("collected_sources", []))

        accepted_counts: dict[tuple[str, str | None], int] = {}
        fetched_counts: dict[tuple[str, str | None], int] = {}
        failed_counts: dict[tuple[str, str | None], int] = {}
        abstract_counts: dict[tuple[str, str | None], int] = {}
        usable = []
        for url in urls_to_scrape:
            res = new_urls_map[url]
            key = (res.provider or "web", res.query)
            if scraped_data.get(url):
                fetched_counts[key] = fetched_counts.get(key, 0) + 1
            else:
                failed_counts[key] = failed_counts.get(key, 0) + 1
        for url in urls_to_scrape:
            res = new_urls_map[url]
            provider = res.provider or "web"
            content = scraped_data.get(url)
            verified_scope = getattr(content, "text_scope", None)
            text_scope = "FULL_TEXT" if verified_scope == "FULL_TEXT" else ("LANDING_PAGE" if res.source_type == "PAPER" else "WEB_PAGE")
            if not content and res.source_type == "PAPER" and len((res.content or "").strip()) >= 80:
                content = res.content.strip()
                text_scope = "ABSTRACT"
            if not content:
                continue
            usable.append((url, res, content, text_scope))
        # Preserve the metadata relevance ordering through successful fetches;
        # do not elevate a landing page merely because fetching it succeeded.
        usable = (balance_by_need(usable, needs, decisions, lambda item: item[0])
                  if any(url in need_hints for url, *_ in usable)
                  else balance_by_query(usable, queries, lambda item: item[1].matched_queries or [item[1].query]))
        for url, res, content, text_scope in usable:
            provider = res.provider or "web"
            if len(new_sources) >= remaining_sources:
                break
            base_idx += 1
            source_tag = f"src_{base_idx:02d}"
            provider_query = (provider, res.query)
            accepted_counts[provider_query] = accepted_counts.get(provider_query, 0) + 1
            if text_scope == "ABSTRACT":
                abstract_counts[provider_query] = abstract_counts.get(provider_query, 0) + 1

            new_sources.append({
                "url": str(res.url),
                "title": res.title,
                "content": content[:200_000],
                "source_tag": source_tag,
                "author": "; ".join(res.authors)[:255] if res.authors else None,
                "publication_date": res.published_date,
                "doi": res.doi,
                "venue": res.venue,
                "search_provider": provider,
                "full_text_url": str(res.full_text_url) if res.full_text_url else None,
                "source_type": res.source_type,
                "text_scope": text_scope,
                "query": res.query,
                "discovery_queries": res.matched_queries or ([res.query] if res.query else []),
            })

        current_iter = state.get("current_iteration", 0) + 1
        await _record_progress(state, "RESEARCHER", current_iter)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Researcher",
            status="SUCCESS",
            iteration=current_iter,
            attempt_number=state.get("attempt_number", 1),
            model="scholarly-and-web-search",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"queries": queries},
            output_summary={"sources_scraped": len(new_sources), "visited_urls": len(urls_to_scrape)},
            tool_calls=[
                {"tool": "scholarly_and_web_search", "queries_count": len(queries)},
                {"tool": "scraper", "scraped_count": len(urls_to_scrape)},
            ],
        )

        from app.services.research_quality import attribute_collection_counts
        collection_activity = attribute_collection_counts(
            provider_activity, completed_at.isoformat(), fetched_count=fetched_counts,
            accepted_count=accepted_counts, fetch_failed_count=failed_counts,
            abstract_only_count=abstract_counts, previously_seen_count=seen_counts,
        )
        return {
            "current_agent": "researcher",
            "collected_sources": new_sources,  # Annotated[list, operator.add]
            "source_selection_log": selection_log,
            "visited_urls": set(urls_to_scrape) | {
                f"doi:{res.doi.casefold().removeprefix('https://doi.org/')}"
                for res in (new_urls_map[url] for url in urls_to_scrape) if res.doi
            }, # URLs and scholarly DOI identities prevent repeat ingestion.
            "search_activity": collection_activity or [{
                "provider": "search providers",
                "queries": queries,
                "candidate_count": len(search_results),
                "fetched_count": len(new_sources),
                "accepted_count": len(new_sources),
                "previously_seen_count": sum(seen_counts.values()),
                "completed_at": completed_at.isoformat(),
                "status": "SUCCESS",
            }],
            "current_iteration": current_iter
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Researcher",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="tavily-search-api",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def curator_node(state: ResearchState) -> Dict[str, Any]:
    """
    Curator Module: Lọc URL trùng lặp, chia nhỏ (Chunking) và nạp vào pgvector.
    Module này chạy code Python 100%, không dùng LLM.
    """
    await _record_progress(state, "CURATOR")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "curator"}

    try:
        task_id = uuid.UUID(task_id_str)
        sources = state.get("collected_sources", [])

        embedder = EmbedderTool()
        chunks_count = 0

        async with AsyncSessionLocal() as db:
            for src in sources:
                # Normalize extracted/search metadata before any PostgreSQL text write.
                for key, value in list(src.items()):
                    if isinstance(value, str) and '\x00' in value:
                        src[key] = value.replace('\x00', ' ')
                if "db_id" in src:
                    if state.get("enforce_provider_budget"):
                        count = await embedder.embed_existing_chunks(
                            db=db,
                            task_id=task_id,
                            source_id=uuid.UUID(src["db_id"]),
                            budget_context={
                                "task_id": state["task_id"],
                                "attempt_number": state.get("attempt_number", 1),
                            },
                        )
                        chunks_count += count
                    continue  # Existing sources are embedded once; later rounds skip their stored vectors.

                # Lưu Source vào DB
                db_source = ResearchSource(
                    research_task_id=task_id,
                    source_tag=src["source_tag"],
                    title=src.get("title", ""),
                    url=src.get("url", ""),
                    author=src.get("author"),
                    publication_date=src.get("publication_date"),
                    doi=src.get("doi"),
                    venue=src.get("venue"),
                    search_provider=src.get("search_provider"),
                    full_text_url=src.get("full_text_url"),
                    source_type=src.get("source_type") or "WEBSITE",
                    content_snippet=src.get("content", "")[:500],
                    text_scope=src.get("text_scope"),
                    discovery_queries=src.get("discovery_queries") or [],
                )
                db.add(db_source)
                await db.flush()  # Để lấy db_source.id
                src["db_id"] = str(db_source.id)

                # Chia chunk và nhúng
                embed_args = {
                    "db": db,
                    "task_id": task_id,
                    "source_id": db_source.id,
                    "text_content": src.get("content", ""),
                }
                if state.get("enforce_provider_budget"):
                    embed_args["budget_context"] = {
                        "task_id": state["task_id"],
                        "attempt_number": state.get("attempt_number", 1),
                    }
                count = await embedder.embed_and_store(**embed_args)
                chunks_count += count

            if state.get("enforce_provider_budget"):
                from app.services.provider_budget import assert_task_active
                await assert_task_active(state["task_id"], state.get("attempt_number", 1))
            await db.commit()

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        embedding_tokens = chunks_count * 256
        cost = estimate_cost("gemini-embedding-2", embedding_tokens, 0)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Curator",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="gemini-embedding-2",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=embedding_tokens,
            output_tokens=0,
            estimated_cost=cost,
            input_summary={"sources_count": len(sources)},
            output_summary={"chunks_indexed": chunks_count},
            tool_calls=[{"tool": "embedder", "chunks_indexed": chunks_count}],
        )

        return {
            "current_agent": "curator",
            "indexed_chunks_count": state.get("indexed_chunks_count", 0) + chunks_count
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Curator",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="gemini-embedding-2",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def analyst_node(state: ResearchState) -> Dict[str, Any]:
    """
    Analyst Agent: Dùng Semantic Search RAG để trích xuất Claims + Evidence từ pgvector.
    """
    await _record_progress(state, "ANALYST")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    import uuid
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    llm = get_fast_llm().with_structured_output(AnalystExtraction)
    embedder = EmbedderTool()

    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "analyst"}

    try:
        task_id = uuid.UUID(task_id_str)
        from app.services.evidence_selection import analysis_needs, evidence_need_coverage
        needs = analysis_needs(state)
        queries = [need["question"] for need in needs]

        all_claims: list[Dict[str, Any]] = []

        # Dùng asyncio.gather để xử lý song song các queries
        async def process_query(need: dict) -> tuple[List[Dict], List[Any]]:
            query = need["question"]
            async with AsyncSessionLocal() as db:
                # RAG: Lấy chunks liên quan nhất cho query từ đa dạng nguồn
                retrieval_limit = 6
                if state.get("enforce_provider_budget"):
                    similar_chunks = await embedder.search_similar_chunks(
                        db, task_id, query, limit=retrieval_limit,
                        budget_context={
                            "task_id": state["task_id"],
                            "attempt_number": state.get("attempt_number", 1),
                        },
                    )
                else:
                    similar_chunks = await embedder.search_similar_chunks(db, task_id, query, limit=retrieval_limit)

                if not similar_chunks:
                    return [], []

                retrieved_chunks = [chunk for chunk, _distance in similar_chunks]
                chunk_context = []
                for chunk in retrieved_chunks:
                    source = await db.scalar(
                        select(ResearchSource).where(
                            ResearchSource.id == chunk.source_id,
                            ResearchSource.research_task_id == task_id,
                        )
                    )
                    if source is not None:
                        chunk_context.append(
                            f"Source tag: {source.source_tag}\n"
                            f"Chunk ID: {chunk.id}\n"
                            f"Source: {source.title or source.url}\n"
                            f"Available text scope: {source.text_scope or 'UNKNOWN'}\n"
                            f"Content: {chunk.content}"
                        )

                # Ghép nội dung
                context_text = "\n\n".join(chunk_context)

                prompt = render_prompt('evidence_analyst',
                    research_question=str(state.get('research_question') or '')[:1000],
                    evidence_need_id=need['need_id'],
                    section_id=need['section_id'],
                    evidence_question=query,
                    source_passages=context_text,
                )

                # An empty, valid extraction means the passages offer no support.
                # A failed model call does not: preserve its error so retries can
                # reuse completed units without burning the rest of the budget.
                extraction = await invoke_llm_with_budget(
                    state, llm, [HumanMessage(content=prompt)], model_name=model_name, output_tokens=4096
                )
                extracted = [{**c.model_dump(), "evidence_need_id": need["need_id"]}
                             for c in extraction.claims]
                return extracted, retrieved_chunks

        # Chạy song song tất cả các queries
        from app.services.model_connection import current_connection
        # Personal/free accounts have smaller quotas. Avoid reserving five large
        # outputs at once or allowing sibling calls to waste the remaining cap.
        if current_connection() is not None:
            results = []
            for need in needs:
                results.append(await process_query(need))
        else:
            tasks = [process_query(need) for need in needs]
            # Drain siblings so provider calls cannot outlive the runtime scope.
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result
        from app.services.grounding import persist_grounded_claims

        if state.get("enforce_provider_budget"):
            from app.services.provider_budget import assert_task_active
            await assert_task_active(state["task_id"], state.get("attempt_number", 1))

        async with AsyncSessionLocal() as db:
            persisted_results = []
            for extracted, retrieved_chunks in results:
                accepted = await persist_grounded_claims(db, task_id, extracted, retrieved_chunks)
                all_claims.extend(accepted)
                persisted_results.append((accepted, retrieved_chunks))
            if state.get("enforce_provider_budget"):
                from app.services.provider_budget import assert_task_active
                await assert_task_active(state["task_id"], state.get("attempt_number", 1))
            await db.commit()
        need_coverage = evidence_need_coverage(needs, persisted_results, [len(extracted) for extracted, _ in results])

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok = max(100, len(queries) * 600)
        out_tok = max(50, len(all_claims) * 50)
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Analyst",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"queries_count": len(queries)},
            output_summary={"verified_claims_count": len(all_claims),
                            "proposed_claims_count": sum(len(extracted) for extracted, _ in results),
                            "distinct_sources": len({c["source_id"] for c in all_claims}),
                            "needs_without_quotes": need_coverage["missing_need_ids"]},
            tool_calls=[{"tool": "semantic_search", "query_count": len(queries)}],
        )

        return {
            "current_agent": "analyst",
            "claims": all_claims,  # Exact-quote matching only; semantic support is reviewed later.
            "evidence_need_coverage": need_coverage,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Analyst",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def methodologist_node(state: ResearchState) -> Dict[str, Any]:
    """
    Methodologist Agent:
    - Thiết lập Đề cương nghiên cứu khoa học (Study Protocol): giả thuyết, biến số, cỡ mẫu, quy trình thu thập.
    - Lưu đề cương thành file Markdown trong ArtifactStore làm tài liệu trung gian (intermediate artifact).
    - Tạo bản ghi ExportArtifact (export_type='PROTOCOL') trong CSDL gắn với task.
    - Nếu research_type == 'EMPIRICAL_HUMAN' và chưa có user_data_submission:
      trạng thái workflow chuyển thành WAITING_USER_DATA để người dùng tiến hành khảo sát/lab thực tế.
    """
    await _record_progress(state, "METHODOLOGIST")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=True)

    task_id_str = state.get("task_id")
    task_uuid = uuid.UUID(task_id_str) if task_id_str else uuid.uuid4()
    research_type = state.get("research_type", "EMPIRICAL_HUMAN")
    user_data = state.get("user_data_submission")

    # Nếu đã có protocol trong state từ trước, tái sử dụng để tiết kiệm chi phí
    existing_protocol = state.get("protocol")
    if existing_protocol and existing_protocol.get("research_questions") and existing_protocol.get("protocol_markdown"):
        logger.info("Methodologist: Reusing existing study protocol for task %s", task_id_str)
        status = "WAITING_USER_DATA" if (research_type == "EMPIRICAL_HUMAN" and not user_data) else "RUNNING"
        return {
            "current_agent": "methodologist",
            "protocol": existing_protocol,
            "protocol_artifact_id": state.get("protocol_artifact_id"),
            "status": status,
        }

    from app.services.study_protocol import protocol_constraints, render_protocol, protocol_fields
    claims = state.get("claims", [])
    prompt = render_prompt('methodologist',
        research_question=state.get('research_question'),
        research_type=research_type,
        output_language=format_language_instruction(state.get('language', 'en')),
        claims=writer_claim_context(claims[:10]),
        protocol_constraints=protocol_constraints(research_type),
    )

    try:
        llm = get_smart_llm().with_structured_output(MethodologistPlan)
        proto_result: MethodologistPlan = await invoke_llm_with_budget(
            state, llm, [HumanMessage(content=prompt)], model_name=model_name, output_tokens=4096
        )
        protocol_dict = protocol_fields(proto_result.model_dump(exclude={'protocol_markdown'}))
        markdown_content = render_protocol(protocol_dict, state.get('language', 'en'))
        protocol_dict["protocol_markdown"] = markdown_content

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(proto_result, prompt_str=prompt, output_str=markdown_content)
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=task_id_str,
            agent_name="Methodologist",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"claims_considered": len(claims)},
            output_summary={
                "hypotheses_count": len(proto_result.hypotheses),
            },
            tool_calls=[{"tool": "generate_protocol"}],
        )

        status = "WAITING_USER_DATA" if (research_type == "EMPIRICAL_HUMAN" and not user_data) else "RUNNING"
        return {
            "current_agent": "methodologist",
            "protocol": protocol_dict,
            "status": status,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=task_id_str,
            agent_name="Methodologist",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def experiment_runner_node(state: ResearchState) -> Dict[str, Any]:
    """LangGraph entry point for the isolated computational study routine."""
    from app.agents.computational_experiment import run_computational_experiment

    return await run_computational_experiment(
        state, record_progress=_record_progress, record_run=record_agent_run,
    )


def _writing_role_services() -> WritingRoleServices:
    return WritingRoleServices(
        record_progress=_record_progress,
        record_agent_run=record_agent_run,
        get_active_model_name=get_active_model_name,
        get_smart_llm=get_smart_llm,
        get_fast_llm=get_fast_llm,
        invoke_llm_with_budget=invoke_llm_with_budget,
        budgeted_llm_type=BudgetedFallbackLLM,
    )


async def writer_node(state: ResearchState) -> Dict[str, Any]:
    """LangGraph entry point for manuscript drafting."""
    return await run_writer(state, _writing_role_services())


async def critic_node(state: ResearchState) -> Dict[str, Any]:
    """LangGraph entry point for bounded academic review."""
    return await run_critic(state, _writing_role_services())


def _format_reference(item, number, style):
    return format_reference(item, number, style)


async def post_processor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Post Processor: Module Regex code để định dạng Markdown cuối cùng và đánh số trích dẫn.
    """
    await _record_progress(state, "POST_PROCESSOR")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    draft = normalize_claim_markers(state.get("draft_report_markdown", ""))

    import re

    try:
        claims_by_id = {
            str(item.get("claim_id")): item
            for item in state.get("claims", [])
            if item.get("claim_id") and item.get("evidence_id")
        }
        marker_pattern = re.compile(r"\[\[@claim:([0-9a-fA-F-]{36})\]\]")
        used_ids: list[str] = []
        for match in marker_pattern.finditer(draft):
            claim_id = match.group(1)
            if claim_id in claims_by_id and claim_id not in used_ids:
                used_ids.append(claim_id)

        source_numbers, citation_numbers, reference_claims = {}, {}, []
        for claim_id in used_ids:
            item = claims_by_id[claim_id]
            source_key = item.get("source_id") or item.get("source_url") or claim_id
            if source_key not in source_numbers:
                source_numbers[source_key] = len(source_numbers) + 1
                reference_claims.append(claim_id)
            citation_numbers[claim_id] = source_numbers[source_key]
        suffixes = reference_suffixes([claims_by_id[cid] for cid in reference_claims], state.get("citation_style", "IEEE"))
        formatted = {claim_id: format_reference(claims_by_id[claim_id], number, state.get("citation_style", "IEEE"),
                    suffix=suffixes.get(reference_identity(claims_by_id[claim_id]), ""))
                     for claim_id, number in citation_numbers.items()}

        def replace_marker(match: re.Match[str]) -> str:
            number = citation_numbers.get(match.group(1))
            return f"@@VALID_CITATION_{number}@@" if number is not None else ""

        final_md = marker_pattern.sub(replace_marker, draft)
        # Several grounded claims can cite the same source consecutively. Keep
        # every claim/evidence record, but print its reference label only once.
        final_md = re.sub(
            r"(@@VALID_CITATION_\d+@@)(?:(?:[ \t]*[,;][ \t]*|[ \t]*)\1)+",
            r"\1", final_md,
        )
        # Remove all model-authored numbered citations, then restore only markers
        # that resolved to validated claim/evidence records.
        final_md = re.sub(r"\[\d+\]", "", final_md)
        for claim_id, number in citation_numbers.items():
            final_md = final_md.replace(f"@@VALID_CITATION_{number}@@", formatted[claim_id][0])
        final_md = re.sub(r"\[\[?@claim:[^\]\n]*\]\]?", "", final_md)
        final_md = re.sub(r"\[\[?@claim:[^\]\n]*$", "", final_md, flags=re.MULTILINE)
        # Discard a model-authored bibliography and construct it from validated sources.
        contract = (state.get("plan") or {}).get("manuscript_contract")
        reference_aliases = ["references", "bibliography", "works cited", "tài liệu tham khảo"]
        if contract:
            reference_aliases.append(contract["references_heading"])
        reference_pattern = "|".join(re.escape(heading) for heading in reference_aliases)
        final_md = re.sub(
            rf"(?ims)^#{{1,3}}\s*(?:\d+[.)]?\s*)?(?:{reference_pattern})\s*$.*\Z",
            "",
            final_md,
        ).rstrip()
        citation_records = [{**claims_by_id[claim_id], "citation_label": formatted[claim_id][0], "citation_number": citation_numbers[claim_id]}
                            for claim_id in used_ids]
        no_grounded_citations = state.get("enforce_provider_budget") and not citation_records
        review_metadata = dict(state.get("critic_review_metadata") or {})
        review_metadata["source_selection_log"] = state.get("source_selection_log") or []
        need_coverage = state.get("evidence_need_coverage") or {}
        from app.services.evidence_selection import blocking_evidence_gaps
        if need_coverage:
            review_metadata["evidence_need_coverage"] = need_coverage
        if ((state.get("plan") or {}).get("evidence_needs") and blocking_evidence_gaps(need_coverage)
                and not state.get("editorial_revision")):
            review_metadata.update(status="NEEDS_REVIEW", evidence_need_findings=[
                "Planned evidence needs lack matched quotes; candidate coverage is not semantic verification."])
        if (contract or {}).get("research_quality_policy") and any(e.get("query") for e in state.get("search_activity", [])) and query_coverage(state)["missing_queries"]:
            review_metadata.update(status="NEEDS_REVIEW", source_query_coverage=query_coverage(state))
        if (contract or {}).get("evidence_review_policy") and not audit_matches_draft(review_metadata, draft):
            review_metadata.update(status="NEEDS_REVIEW", evidence_delivery_findings=[
                "A complete, supporting evidence review for this exact draft is unavailable."])
        bibliography_notes = reference_metadata_notes([claims_by_id[cid] for cid in reference_claims])
        review_metadata["reference_metadata_notes"] = bibliography_notes
        title_metadata_findings = [item for item in bibliography_notes
                                   if {"title", "title_may_be_internal_source_label"} & set(item.get("missing", []))]
        if title_metadata_findings:
            review_metadata.update(status="NEEDS_REVIEW", bibliography_findings=[
                "At least one cited source has no trustworthy publication title. Resolve its metadata before presenting the bibliography as publication-ready."
            ])
        from copy import deepcopy
        review_metadata["manuscript_input_snapshot"] = {key:deepcopy(state.get(key)) for key in (
            "research_type", "language", "citation_style", "report_length", "plan", "protocol",
            "user_data_submission", "analysis_run")}
        if state.get("editorial_revision"):
            review_metadata["revision"] = deepcopy(state.get("revision_info") or {})
        review_metadata["bibliography_snapshot"] = [{key: item.get(key) for key in (
            "source_id", "source_title", "source_url", "source_author", "publication_date",
            "venue", "doi", "citation_label"
        )} for item in citation_records]
        if no_grounded_citations:
            review_metadata.update(status="NEEDS_REVIEW", delivery_findings=["The manuscript contains no validated source citations."])
        if citation_records:
            reference_heading = contract["references_heading"] if contract else "References"
            references = ["", f"## {reference_heading}", ""]
            for claim_id in reference_claims:
                references.append(formatted[claim_id][1])
            final_md += "\n".join(references)

        contract = (state.get("plan") or {}).get("manuscript_contract")
        manuscript_findings = validate_manuscript(final_md, contract)
        figures = state.get("scientific_figures") or []
        final_md = materialize_figures(final_md, figures)
        scientific_review_context = {
            **(state.get("scientific_context") or {}),
            "used_source_count": len({str(item.get("source_id")) for item in citation_records if item.get("source_id")}),
        }
        manuscript_findings += validate_scientific_reporting(final_md, contract, scientific_review_context, figures)
        lineage_findings = _claim_lineage_findings(draft, state.get("claims", []))
        if contract:
            review_metadata.update(manuscript_contract=contract, method_provenance=manuscript_provenance(state))
            review_metadata.update(scientific_context=scientific_review_context, scientific_figures=figures)
        if manuscript_findings:
            review_metadata.update(status="NEEDS_REVIEW", manuscript_findings=manuscript_findings)
        if lineage_findings:
            review_metadata.update(status="NEEDS_REVIEW", lineage_findings=lineage_findings)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="PostProcessor",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="deterministic-regex-processor",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"used_claims_count": len(used_ids)},
            output_summary={"citations_count": len(citation_records), "report_words": len(final_md.split())},
            tool_calls=[],
        )

        return {
            "current_agent": "post_processor",
            "final_report_markdown": final_md,
            "citations": citation_records,
            "status": "NEEDS_REVIEW" if review_metadata.get("status") == "NEEDS_REVIEW" or lineage_findings or manuscript_findings or no_grounded_citations or state.get("draft_truncated") or state.get("critic_verdict") in {"NEEDS_REVIEW", "NEED_MORE_DATA", "REVISE"} else "COMPLETED",
            "critic_review_metadata": review_metadata,
            "citation_validation": {
                "valid_citations": len(citation_records),
                "unresolved_markers": len(lineage_findings),
            },
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="PostProcessor",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="deterministic-regex-processor",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise
