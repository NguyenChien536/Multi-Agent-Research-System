"""Run the fixed, project-owned numeric routine in a fresh bounded process.

This is not a sandbox for arbitrary or model-generated code. The subprocess can
only invoke the fixed allowlisted tabular_regression_v1 implementation.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from app.services.experiment_runner import ExperimentError


RUNNER_TIMEOUT_SECONDS = 120
MAX_RUNNER_OUTPUT_BYTES = 1_000_000


async def _invoke(payload: dict[str, Any], timeout_seconds: int = RUNNER_TIMEOUT_SECONDS) -> dict[str, Any]:
    project_root = str(Path(__file__).resolve().parents[2])
    minimal_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": project_root,
        "PYTHONIOENCODING": "utf-8",
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.services.experiment_runner",
        cwd=project_root,
        env=minimal_env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise ExperimentError(f"Isolated analysis exceeded {timeout_seconds} seconds and was terminated") from exc
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise

    if len(stdout) > MAX_RUNNER_OUTPUT_BYTES:
        raise ExperimentError("Isolated analysis output exceeded the allowed size")
    if process.returncode != 0:
        try:
            error = json.loads(stderr.decode("utf-8", errors="replace"))
            detail = f"{error.get('error_type', 'RunnerError')}: {error.get('error', 'analysis failed')}"
        except Exception:
            detail = stderr.decode("utf-8", errors="replace")[:500] or f"exit code {process.returncode}"
        raise ExperimentError(detail)
    try:
        result = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentError("Isolated analysis returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ExperimentError("Isolated analysis returned an invalid result shape")
    return result


async def run_tabular_regression_isolated(
    dataset_csv: str,
    *,
    target_column: str,
    feature_columns: list[str],
    alpha: float = 1.0,
    test_size: float = 0.2,
    seed: int = 42,
) -> dict[str, Any]:
    return await _invoke({
        "action": "run",
        "dataset_csv": dataset_csv,
        "target_column": target_column,
        "feature_columns": feature_columns,
        "alpha": alpha,
        "test_size": test_size,
        "seed": seed,
    })


async def verify_tabular_repeatability_isolated(
    dataset_csv: str,
    original_result: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    result = await _invoke({
        "action": "verify",
        "dataset_csv": dataset_csv,
        "original_result": original_result,
    })
    if not isinstance(result.get("passed"), bool) or not isinstance(result.get("diff"), dict):
        raise ExperimentError("Isolated repeatability check returned an invalid result shape")
    return result["passed"], result["diff"]
