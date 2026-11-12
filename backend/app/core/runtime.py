"""Task-local dependency overrides for controlled workflow execution.

Normal requests use the existing providers. A bound runtime supplies all external
boundaries together; ContextVar tokens must be reset even on cancellation.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WorkflowRuntime:
    sessions: Callable
    llm: Any
    model_name: str
    invoke: Callable
    search: Callable
    fetch: Callable
    embedder: Callable
    progress: Callable


_runtime: ContextVar[WorkflowRuntime | None] = ContextVar("workflow_runtime", default=None)


def current_runtime() -> WorkflowRuntime | None:
    return _runtime.get()


@contextmanager
def workflow_runtime(runtime: WorkflowRuntime):
    token = _runtime.set(runtime)
    try:
        yield runtime
    finally:
        _runtime.reset(token)
