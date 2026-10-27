"""One asyncio loop per Celery child, shared by every job in that process."""
import asyncio
import os
from collections.abc import Coroutine
from typing import Any

from celery.signals import worker_process_shutdown

_runner: asyncio.Runner | None = None
_runner_pid: int | None = None


def run_worker_coroutine(coroutine: Coroutine[Any, Any, Any]):
    global _runner, _runner_pid
    pid = os.getpid()
    if _runner is None or _runner_pid != pid:
        _runner = asyncio.Runner()
        _runner_pid = pid
    return _runner.run(coroutine)


@worker_process_shutdown.connect
def close_worker_runtime(**_kwargs):
    global _runner, _runner_pid
    if _runner is not None and _runner_pid == os.getpid():
        from app.core.database import engine
        try:
            _runner.run(engine.dispose())
        finally:
            _runner.close()
            _runner, _runner_pid = None, None
