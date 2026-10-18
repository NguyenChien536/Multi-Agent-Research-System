"""Service for recording agent run execution history, token usage, and cost accounting."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun

logger = logging.getLogger(__name__)

# Pricing table per 1,000,000 tokens (USD)
# Source: official provider pricing as of 2024-2026
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Gemini
    "gemini-3.5-flash-lite": {"prompt": 0.075, "completion": 0.30},
    "gemini-2.5-flash-lite": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-3.5-flash": {"prompt": 0.15, "completion": 0.60},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
    "gemini-embedding-2": {"prompt": 0.02, "completion": 0.0},
    # OpenAI
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
    # Anthropic
    "claude-3-5-haiku-20241022": {"prompt": 0.80, "completion": 4.00},
    "claude-3-5-sonnet-20240620": {"prompt": 3.00, "completion": 15.00},
    # Groq / Open Source
    "llama-3.1-8b-instant": {"prompt": 0.05, "completion": 0.08},
}

DEFAULT_PRICING = {"prompt": 0.15, "completion": 0.60}


def get_active_model_name(is_smart: bool = False) -> str:
    """Determine the active model name based on provider priority and tier."""
    providers = [p.strip().lower() for p in settings.LLM_PROVIDER_PRIORITY.split(",")]
    primary_provider = providers[0] if providers else "gemini"

    if primary_provider == "gemini":
        return "gemini-3.5-flash" if is_smart else "gemini-3.5-flash-lite"
    elif primary_provider == "openai":
        return "gpt-4o" if is_smart else "gpt-4o-mini"
    elif primary_provider == "anthropic":
        return "claude-3-5-sonnet-20240620" if is_smart else "claude-3-5-haiku-20241022"
    elif primary_provider == "groq":
        return "llama-3.1-8b-instant"
    return "gemini-3.5-flash" if is_smart else "gemini-3.5-flash-lite"


def estimate_cost(model_name: Optional[str], input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD based on model pricing per 1M tokens."""
    if not model_name:
        pricing = DEFAULT_PRICING
    else:
        # Normalize model name for fuzzy matching
        clean_model = model_name.lower()
        pricing = DEFAULT_PRICING
        for key, p in MODEL_PRICING.items():
            if key in clean_model:
                pricing = p
                break

    cost = (input_tokens / 1_000_000.0) * pricing["prompt"] + (output_tokens / 1_000_000.0) * pricing["completion"]
    return round(cost, 6)


def extract_tokens(
    response: Any,
    prompt_str: str = "",
    output_str: str = "",
) -> Tuple[int, int]:
    """Extract or estimate input and output token counts from a model response or text."""
    input_tokens = 0
    output_tokens = 0

    if response is not None:
        # Check usage_metadata (standard in modern LangChain)
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

        # Check response_metadata
        if input_tokens == 0 and output_tokens == 0:
            meta = getattr(response, "response_metadata", None)
            if isinstance(meta, dict):
                token_usage = meta.get("token_usage") or meta.get("usage") or {}
                if isinstance(token_usage, dict):
                    input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0)
                    output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0)

    # Heuristic fallback if metadata is absent
    if input_tokens == 0 and prompt_str:
        input_tokens = max(1, len(prompt_str) // 4)
    if output_tokens == 0 and output_str:
        output_tokens = max(1, len(output_str) // 4)

    return input_tokens, output_tokens


async def record_agent_run(
    task_id: Optional[str],
    agent_name: str,
    status: str = "SUCCESS",
    iteration: int = 0,
    attempt_number: int = 1,
    model: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    duration_ms: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost: float = 0.0,
    input_summary: Optional[Dict[str, Any]] = None,
    output_summary: Optional[Dict[str, Any]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    error_message: Optional[str] = None,
) -> Optional[uuid.UUID]:
    """Persist an individual agent run execution record into the database."""
    if not task_id:
        return None

    try:
        parsed_task_id = uuid.UUID(str(task_id))
    except (TypeError, ValueError):
        logger.warning("Ignoring agent run record with invalid task_id: %s", task_id)
        return None

    now = datetime.now(timezone.utc)
    run_record = AgentRun(
        research_task_id=parsed_task_id,
        agent_name=agent_name,
        status=status,
        iteration=iteration,
        attempt_number=attempt_number or 1,
        model=model,
        started_at=started_at or now,
        completed_at=completed_at or now,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        input_summary=input_summary or {},
        output_summary=output_summary or {},
        tool_calls=tool_calls or [],
        error_message=error_message,
    )

    try:
        async with AsyncSessionLocal() as session:
            session.add(run_record)
            await session.commit()
            return run_record.id
    except Exception as exc:
        logger.warning("Failed to persist AgentRun for task %s, agent %s: %s", task_id, agent_name, exc)
        return None
