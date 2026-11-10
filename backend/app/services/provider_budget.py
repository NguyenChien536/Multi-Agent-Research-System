"""Durable, fail-closed budget checks immediately before provider requests."""

import logging
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.models.user import User
from app.services.agent_run import MODEL_PRICING, estimate_cost

logger = logging.getLogger(__name__)

HARD_MAX_LLM_CALLS = 60
HARD_MAX_COST_USD = 2.0
HARD_MAX_ACTIVE_SECONDS = 3600
HARD_MAX_INPUT_TOKENS = 300_000
HARD_MAX_OUTPUT_TOKENS = 200_000
DEFAULT_CALL_OUTPUT_TOKENS = 4096


class ProviderBudgetExceeded(RuntimeError):
    """The research task cannot make another provider request within its budget."""


class ResearchTaskStopped(RuntimeError):
    """The worker no longer owns a running task (cancelled or superseded)."""


def retry_block_reason(task, *, ignore_stop_marker: bool = False) -> str | None:
    """Expose a safe action decision, never credentials or raw reservation data."""
    if not ignore_stop_marker and getattr(task, 'current_step', None) == 'BUDGET_LIMIT':
        return 'TASK_BUDGET_LIMIT'
    config = getattr(task, 'budget_config', None) or {}
    usage = _usage(config)
    calls, inputs, outputs, cost, seconds = _limits(config)
    if any((usage.get(key, 0) >= limit) for key, limit in (
        ('llm_calls', calls), ('input_tokens', inputs), ('output_tokens', outputs),
        ('cost_usd', cost), ('active_seconds', seconds))):
        return 'TASK_BUDGET_LIMIT'
    return None


def token_allowance_summary(task) -> dict:
    """Public counters and an explicit, bounded continuation offer; never keys."""
    config = pause_budget_config(getattr(task, 'budget_config', None), now=getattr(task, 'completed_at', None))
    usage = _usage(config)
    calls, inputs, outputs, cost, seconds = _limits(config)
    reserved_in = sum(int(v.get('input_tokens', 0)) for v in usage['reservations'].values())
    reserved_out = sum(int(v.get('output_tokens', 0)) for v in usage['reservations'].values())
    remaining_in = max(0, inputs - int(usage.get('input_tokens', 0)) - reserved_in)
    remaining_out = max(0, outputs - int(usage.get('output_tokens', 0)) - reserved_out)
    call_output = min(16384, (((config.get('_llm_connection') or {}).get('profile') or {}).get('output_token_limit') or 8192))
    eligible = getattr(task, 'status', '') == 'FAILED' or (
        getattr(task, 'status', '') == 'NEEDS_REVIEW' and getattr(task, 'current_step', None) == 'BUDGET_LIMIT')
    next_calls = min(calls + 10, HARD_MAX_LLM_CALLS) if usage.get('llm_calls', 0) >= calls else calls
    next_seconds = min(seconds + 900, HARD_MAX_ACTIVE_SECONDS) if usage.get('active_seconds', 0) >= seconds else seconds
    other_limits_ok = (usage.get('cost_usd', 0) < cost
                       and (usage.get('llm_calls', 0) < calls or next_calls > calls)
                       and (usage.get('active_seconds', 0) < seconds or next_seconds > seconds))
    next_in = min(inputs + 100_000, HARD_MAX_INPUT_TOKENS)
    next_out = min(outputs + 50_000, HARD_MAX_OUTPUT_TOKENS)
    return {'input_used': int(usage.get('input_tokens', 0)), 'output_used': int(usage.get('output_tokens', 0)),
            'max_input_tokens': inputs, 'max_output_tokens': outputs,
            'next_input_tokens': next_in, 'next_output_tokens': next_out,
            'calls_used': int(usage.get('llm_calls', 0)), 'active_seconds_used': float(usage.get('active_seconds', 0)),
            'next_max_llm_calls': next_calls, 'next_timeout_seconds': next_seconds,
            'max_cost_usd': cost,
            'can_extend': bool(eligible and other_limits_ok and (next_in > inputs or next_out > outputs or next_calls > calls or next_seconds > seconds)
                               and (getattr(task, 'current_step', None) == 'BUDGET_LIMIT'
                                    or remaining_out < int(call_output) or remaining_in < 1000
                                    or next_calls > calls or next_seconds > seconds))}


def increase_token_allowance(config: dict, max_input_tokens: int, max_output_tokens: int,
                             *, max_llm_calls: int | None = None, timeout_seconds: int | None = None) -> dict:
    """Explicitly raise resource ceilings; retain all usage and the money limit."""
    old_calls, old_in, old_out, _, old_seconds = _limits(config)
    new_calls = old_calls if max_llm_calls is None else max_llm_calls
    new_seconds = old_seconds if timeout_seconds is None else timeout_seconds
    if not (old_in <= max_input_tokens <= HARD_MAX_INPUT_TOKENS
            and old_out <= max_output_tokens <= HARD_MAX_OUTPUT_TOKENS
            and old_calls <= new_calls <= HARD_MAX_LLM_CALLS
            and old_seconds <= new_seconds <= HARD_MAX_ACTIVE_SECONDS
            and (max_input_tokens > old_in or max_output_tokens > old_out or new_calls > old_calls or new_seconds > old_seconds)):
        raise ValueError('Increase at least one resource limit without lowering another limit or exceeding the maximum.')
    result = deepcopy(config)
    changes = list(result.get('_allowance_changes') or [])
    changes.append({'at': datetime.now(timezone.utc).isoformat(), 'input_before': old_in, 'output_before': old_out,
                    'input_after': max_input_tokens, 'output_after': max_output_tokens,
                    'calls_before': old_calls, 'calls_after': new_calls,
                    'seconds_before': old_seconds, 'seconds_after': new_seconds})
    return {**result, 'max_input_tokens': max_input_tokens, 'max_output_tokens': max_output_tokens,
            'max_llm_calls': new_calls, 'timeout_seconds': new_seconds,
            '_allowance_changes': changes[-10:]}


def _usage(config: dict[str, Any]) -> dict[str, Any]:
    usage = config.get("_provider_usage")
    if not isinstance(usage, dict):
        usage = {
            "llm_calls": 0,
            "search_calls": 0,
            "embedding_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "active_seconds": 0.0,
            "active_since": None,
            "reservations": {},
        }
    usage.setdefault("reservations", {})
    return usage


def pause_budget_config(config: dict[str, Any] | None, *, now: datetime | None = None) -> dict[str, Any]:
    """Freeze active elapsed time while a task is cancelled or waiting for the user."""
    result = deepcopy(config or {})
    usage = _usage(result)
    started = usage.get("active_since")
    if started:
        elapsed = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(started)).total_seconds()
        usage["active_seconds"] = max(0.0, float(usage.get("active_seconds", 0)) + elapsed)
        usage["active_since"] = None
    result["_provider_usage"] = usage
    return result


def _limits(config: dict[str, Any]) -> tuple[int, int, int, float, int]:
    """Apply product hard caps even to old tasks or stale client-supplied values."""
    return (
        min(int(config.get("max_llm_calls", 40)), HARD_MAX_LLM_CALLS),
        min(int(config.get("max_input_tokens", 100_000)), HARD_MAX_INPUT_TOKENS),
        min(int(config.get("max_output_tokens", 50_000)), HARD_MAX_OUTPUT_TOKENS),
        min(float(config.get("max_cost_usd", HARD_MAX_COST_USD)), HARD_MAX_COST_USD),
        min(int(config.get("timeout_seconds", 900)), HARD_MAX_ACTIVE_SECONDS),
    )


async def resume_active_clock(task_id: uuid.UUID | str) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(ResearchTask).where(ResearchTask.id == task_id).with_for_update(key_share=True)
        )
        if task is None:
            return
        config = deepcopy(task.budget_config or {})
        usage = _usage(config)
        if not usage.get("active_since"):
            usage["active_since"] = datetime.now(timezone.utc).isoformat()
            config["_provider_usage"] = usage
            task.budget_config = config
            await session.commit()


async def pause_active_clock(task_id: uuid.UUID | str) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(ResearchTask).where(ResearchTask.id == task_id).with_for_update(key_share=True)
        )
        if task is None:
            return
        config = deepcopy(task.budget_config or {})
        usage = _usage(config)
        started = usage.get("active_since")
        if started:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
            usage["active_seconds"] = max(0.0, float(usage.get("active_seconds", 0)) + elapsed)
            usage["active_since"] = None
            config["_provider_usage"] = usage
            task.budget_config = config
            await session.commit()


async def remaining_active_seconds(task_id: uuid.UUID | str) -> float:
    """A real deadline also bounds a provider that never returns to a budget check."""
    async with AsyncSessionLocal() as session:
        task = await session.get(ResearchTask, uuid.UUID(str(task_id)))
        if task is None or task.status != "RUNNING":
            raise ResearchTaskStopped("Research task is no longer running")
        config = task.budget_config or {}
        usage = _usage(config)
        elapsed = float(usage.get("active_seconds", 0))
        if usage.get("active_since"):
            elapsed += (datetime.now(timezone.utc) - datetime.fromisoformat(usage["active_since"])).total_seconds()
        remaining = _limits(config)[4] - elapsed
        if remaining <= 0:
            raise ProviderBudgetExceeded("Active research time budget exhausted")
        return remaining


def _check_active(task: ResearchTask, usage: dict[str, Any], limits: tuple[int, int, int, float, int]) -> None:
    if task.status != "RUNNING":
        raise ResearchTaskStopped(f"Research task is {task.status}; provider call was stopped")
    since = usage.get("active_since")
    elapsed = float(usage.get("active_seconds", 0))
    if since:
        elapsed += (datetime.now(timezone.utc) - datetime.fromisoformat(since)).total_seconds()
    if elapsed >= limits[4]:
        raise ProviderBudgetExceeded("Active research time budget exhausted")


async def personal_output_capacity(task_id: str | uuid.UUID, requested: int) -> int:
    """Fit a personal model's ceiling to the remaining article allowance.

    This is a preview, not admission. The subsequent atomic reservation still
    checks concurrent reservations, ownership, attempt, cost, calls and time.
    """
    async with AsyncSessionLocal() as session:
        task = await session.get(ResearchTask, uuid.UUID(str(task_id)))
        if task is None:
            raise ResearchTaskStopped("Research task no longer exists")
        usage = _usage(task.budget_config or {})
        reserved = sum(int(v.get('output_tokens', 0)) for v in usage['reservations'].values())
        available = _limits(task.budget_config or {})[2] - int(usage.get('output_tokens', 0)) - reserved
        if available < 1024:
            raise ProviderBudgetExceeded("Insufficient output token allowance for another model response")
        return min(int(requested), available)


async def reserve_provider_call(
    *,
    task_id: str | uuid.UUID,
    attempt_number: int,
    kind: str,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    fixed_cost_usd: float | None = None,
    allow_pre_run: bool = False,
    allow_post_run: bool = False,
) -> str:
    """Atomically reserve one provider attempt. Retries must call this again."""
    parsed_id = uuid.UUID(str(task_id))
    reservation_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(ResearchTask).join(User).where(ResearchTask.id == parsed_id, User.deleted_at.is_(None)).with_for_update(of=ResearchTask, key_share=True)
        )
        if task is None:
            raise ResearchTaskStopped("Research task no longer exists")
        allowed_pre_run = {"PENDING", "WAITING_APPROVAL", "WAITING_USER_DATA"}
        status_allowed = (task.status in {"COMPLETED", "NEEDS_REVIEW", "PARTIAL"}) if allow_post_run else (
            task.status == "RUNNING" or (allow_pre_run and task.status in allowed_pre_run)
        )
        if not status_allowed or task.attempt_number != attempt_number:
            raise ResearchTaskStopped("Research task was cancelled or this worker attempt is stale")
        if task.status == "RUNNING" and task.worker_lease_until and task.worker_lease_until <= datetime.now(timezone.utc):
            raise ResearchTaskStopped("Worker lease expired; provider call was stopped")

        config = deepcopy(task.budget_config or {})
        usage = _usage(config)
        limits = _limits(config)
        if task.status == "RUNNING":
            _check_active(task, usage, limits)

        input_tokens = max(0, int(input_tokens))
        output_tokens = max(0, int(output_tokens))
        from app.services.model_connection import open_connection
        connection = open_connection(config, task.id, task.user_id)
        if kind == "llm":
            if connection is not None:
                if model != connection.model_tag:
                    raise ProviderBudgetExceeded("Only the task owner's configured model may be called")
                call_cost = connection.estimate(input_tokens, output_tokens)
            elif not model or model.startswith("byok:") or not any(key in model.lower() for key in MODEL_PRICING):
                raise ProviderBudgetExceeded("Cannot price an unidentified LLM; provider call blocked")
            else:
                call_cost = estimate_cost(model, input_tokens, output_tokens)
            next_llm_calls = int(usage.get("llm_calls", 0)) + 1
            if next_llm_calls > limits[0]:
                raise ProviderBudgetExceeded(f"LLM call limit reached ({limits[0]})")
        elif kind == "embedding":
            if connection is not None:
                raise ProviderBudgetExceeded("Server embedding credentials are disabled for custom API tasks")
            if not model or not any(key in model.lower() for key in MODEL_PRICING):
                raise ProviderBudgetExceeded("Cannot price unidentified embeddings; provider call blocked")
            call_cost = estimate_cost(model, input_tokens, 0)
            next_embedding_calls = int(usage.get("embedding_calls", 0)) + 1
        elif kind == "search":
            if connection is not None and (model not in {"public:crossref", "public:openalex"} or fixed_cost_usd != 0):
                raise ProviderBudgetExceeded("Custom API tasks use only unkeyed scholarly discovery")
            public_search = model in {"public:crossref", "public:openalex"} and fixed_cost_usd == 0
            if not public_search and (fixed_cost_usd is None or fixed_cost_usd <= 0):
                raise ProviderBudgetExceeded("Search price is unknown; configure a positive per-request ceiling")
            call_cost = float(fixed_cost_usd)
            next_search_calls = int(usage.get("search_calls", 0)) + 1
        else:
            raise ValueError(f"Unsupported provider call kind: {kind}")

        reserved_input = sum(int(item["input_tokens"]) for item in usage["reservations"].values())
        reserved_output = sum(int(item["output_tokens"]) for item in usage["reservations"].values())
        reserved_cost = sum(float(item["cost_usd"]) for item in usage["reservations"].values())
        if int(usage.get("input_tokens", 0)) + reserved_input + input_tokens > limits[1]:
            raise ProviderBudgetExceeded("Input token budget exhausted")
        if int(usage.get("output_tokens", 0)) + reserved_output + output_tokens > limits[2]:
            raise ProviderBudgetExceeded("Output token budget exhausted")
        if float(usage.get("cost_usd", 0)) + reserved_cost + call_cost > limits[3]:
            raise ProviderBudgetExceeded(f"Estimated provider cost budget exhausted (${limits[3]:.2f})")

        if kind == "llm":
            usage["llm_calls"] = next_llm_calls
        elif kind == "embedding":
            usage["embedding_calls"] = next_embedding_calls
        else:
            usage["search_calls"] = next_search_calls

        usage["reservations"][reservation_id] = {
            "kind": kind,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": call_cost,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        config["_provider_usage"] = usage
        task.budget_config = config
        await session.commit()
    return reservation_id


async def settle_provider_call(
    *,
    task_id: str | uuid.UUID,
    reservation_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    succeeded: bool,
    rejected: bool = False,
    usage_reported: bool = False,
) -> None:
    """Reconcile measured completions/rejections; uncertain failures consume the reservation.

    Admission already counted the call. A rejection never restores that call
    allowance or changes provider pacing and never resets previous usage.
    A completed response with invalid JSON still incurs its reported usage;
    usage_reported must only be set when transport usage metadata is present.
    """
    parsed_id = uuid.UUID(str(task_id))
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(ResearchTask).where(ResearchTask.id == parsed_id).with_for_update(key_share=True)
        )
        if task is None:
            return
        config = deepcopy(task.budget_config or {})
        usage = _usage(config)
        reservation = usage["reservations"].pop(reservation_id, None)
        if reservation is None:
            return
        if succeeded or rejected or usage_reported:
            input_tokens = max(0, int(input_tokens))
            output_tokens = max(0, int(output_tokens))
            cost_usd = max(0.0, float(cost_usd))
        else:
            input_tokens = int(reservation["input_tokens"])
            output_tokens = int(reservation["output_tokens"])
            cost_usd = float(reservation["cost_usd"])
        usage["input_tokens"] = int(usage.get("input_tokens", 0)) + input_tokens
        usage["output_tokens"] = int(usage.get("output_tokens", 0)) + output_tokens
        usage["cost_usd"] = round(float(usage.get("cost_usd", 0)) + cost_usd, 8)
        config["_provider_usage"] = usage
        task.budget_config = config
        # Update visible counters at settlement, including pauses and post-run Q&A.
        task.total_tokens_used = usage["input_tokens"] + usage["output_tokens"]
        task.total_cost_usd = round(usage["cost_usd"], 4)
        await session.commit()


async def assert_task_active(
    task_id: str | uuid.UUID,
    attempt_number: int,
    allow_pre_run: bool = False,
    allow_post_run: bool = False,
) -> None:
    """Check task ownership before persisting workflow side effects."""
    parsed_id = uuid.UUID(str(task_id))
    async with AsyncSessionLocal() as session:
        task = await session.scalar(select(ResearchTask).join(User).where(ResearchTask.id == parsed_id, User.deleted_at.is_(None)))
        allowed_pre_run = {"PENDING", "WAITING_APPROVAL", "WAITING_USER_DATA"}
        if task is None:
            raise ResearchTaskStopped("Research task no longer exists")
        status_allowed = (task.status in {"COMPLETED", "NEEDS_REVIEW", "PARTIAL"}) if allow_post_run else (
            task.status == "RUNNING" or (allow_pre_run and task.status in allowed_pre_run)
        )
        if not status_allowed or task.attempt_number != attempt_number:
            raise ResearchTaskStopped("Research task was cancelled or this worker attempt is stale")
        if (
            task.status == "RUNNING"
            and task.worker_lease_until
            and task.worker_lease_until <= datetime.now(timezone.utc)
        ):
            raise ResearchTaskStopped("Worker lease expired; workflow side effect was stopped")


def estimate_tokens(text: str) -> int:
    """Conservative prompt-size estimate used before provider calls."""
    return max(1, (len(text) + 2) // 3) if text else 1
