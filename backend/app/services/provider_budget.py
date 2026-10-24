"""Durable, fail-closed budget checks immediately before provider requests."""

import logging
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.services.agent_run import MODEL_PRICING, estimate_cost

logger = logging.getLogger(__name__)

HARD_MAX_LLM_CALLS = 40
HARD_MAX_COST_USD = 2.0
HARD_MAX_ACTIVE_SECONDS = 900
DEFAULT_CALL_OUTPUT_TOKENS = 4096


class ProviderBudgetExceeded(RuntimeError):
    """The research task cannot make another provider request within its budget."""


class ResearchTaskStopped(RuntimeError):
    """The worker no longer owns a running task (cancelled or superseded)."""


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


def pause_budget_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Freeze active elapsed time while a task is cancelled or waiting for the user."""
    result = deepcopy(config or {})
    usage = _usage(result)
    started = usage.get("active_since")
    if started:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
        usage["active_seconds"] = max(0.0, float(usage.get("active_seconds", 0)) + elapsed)
        usage["active_since"] = None
    result["_provider_usage"] = usage
    return result


def _limits(config: dict[str, Any]) -> tuple[int, int, int, float, int]:
    """Apply product hard caps even to old tasks or stale client-supplied values."""
    return (
        min(int(config.get("max_llm_calls", HARD_MAX_LLM_CALLS)), HARD_MAX_LLM_CALLS),
        min(int(config.get("max_input_tokens", 100_000)), 100_000),
        min(int(config.get("max_output_tokens", 50_000)), 50_000),
        min(float(config.get("max_cost_usd", HARD_MAX_COST_USD)), HARD_MAX_COST_USD),
        min(int(config.get("timeout_seconds", HARD_MAX_ACTIVE_SECONDS)), HARD_MAX_ACTIVE_SECONDS),
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


def _check_active(task: ResearchTask, usage: dict[str, Any], limits: tuple[int, int, int, float, int]) -> None:
    if task.status != "RUNNING":
        raise ResearchTaskStopped(f"Research task is {task.status}; provider call was stopped")
    since = usage.get("active_since")
    elapsed = float(usage.get("active_seconds", 0))
    if since:
        elapsed += (datetime.now(timezone.utc) - datetime.fromisoformat(since)).total_seconds()
    if elapsed >= limits[4]:
        raise ProviderBudgetExceeded("Active research time budget exhausted")


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
) -> str:
    """Atomically reserve one provider attempt. Retries must call this again."""
    parsed_id = uuid.UUID(str(task_id))
    reservation_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(ResearchTask).where(ResearchTask.id == parsed_id).with_for_update(key_share=True)
        )
        if task is None:
            raise ResearchTaskStopped("Research task no longer exists")
        allowed_pre_run = {"PENDING", "WAITING_APPROVAL", "WAITING_USER_DATA"}
        status_allowed = task.status == "RUNNING" or (allow_pre_run and task.status in allowed_pre_run)
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
        if kind == "llm":
            if not model or not any(key in model.lower() for key in MODEL_PRICING):
                raise ProviderBudgetExceeded("Cannot price an unidentified LLM; provider call blocked")
            call_cost = estimate_cost(model, input_tokens, output_tokens)
            next_llm_calls = int(usage.get("llm_calls", 0)) + 1
            if next_llm_calls > limits[0]:
                raise ProviderBudgetExceeded(f"LLM call limit reached ({limits[0]})")
        elif kind == "embedding":
            if not model or not any(key in model.lower() for key in MODEL_PRICING):
                raise ProviderBudgetExceeded("Cannot price unidentified embeddings; provider call blocked")
            call_cost = estimate_cost(model, input_tokens, 0)
            next_embedding_calls = int(usage.get("embedding_calls", 0)) + 1
        elif kind == "search":
            if fixed_cost_usd is None or fixed_cost_usd <= 0:
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
) -> None:
    """Reconcile a completed call; failed/uncertain calls consume their reservation."""
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
        if succeeded:
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
        await session.commit()


async def assert_task_active(
    task_id: str | uuid.UUID,
    attempt_number: int,
    allow_pre_run: bool = False,
) -> None:
    """Check task ownership before persisting workflow side effects."""
    parsed_id = uuid.UUID(str(task_id))
    async with AsyncSessionLocal() as session:
        task = await session.scalar(select(ResearchTask).where(ResearchTask.id == parsed_id))
        allowed_pre_run = {"PENDING", "WAITING_APPROVAL", "WAITING_USER_DATA"}
        if task is None:
            raise ResearchTaskStopped("Research task no longer exists")
        status_allowed = task.status == "RUNNING" or (allow_pre_run and task.status in allowed_pre_run)
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
