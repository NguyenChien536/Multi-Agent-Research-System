"""Runtime dependencies passed to the writing and review roles."""

from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class WritingRoleServices:
    """Runtime calls supplied by the graph entry points; easy to replace in tests."""

    record_progress: Callable[..., Any]
    record_agent_run: Callable[..., Any]
    get_active_model_name: Callable[..., str]
    get_smart_llm: Callable[..., Any]
    get_fast_llm: Callable[..., Any]
    invoke_llm_with_budget: Callable[..., Any]
    budgeted_llm_type: type
