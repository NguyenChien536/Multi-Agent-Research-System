"""Fail before consuming jobs when a stale image lacks required dependencies."""
import importlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REQUIRED_IMPORTS = (
    "langgraph.checkpoint.postgres.aio", "psycopg", "asyncpg",
)


def validate_worker_runtime():
    for module in REQUIRED_IMPORTS:
        importlib.import_module(module)
    # The development source is bind mounted: compare it to installed packages,
    # otherwise restarting an old container silently combines two runtimes.
    lockfile = Path(__file__).resolve().parents[2] / "requirements.lock.txt"
    if lockfile.exists():
        for line in lockfile.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith((" ", "#", "-")) and "==" in line:
                package, pinned = line.split("==", 1)
                pinned = pinned.split()[0]
                try:
                    installed = version(package)
                except PackageNotFoundError as exc:
                    raise RuntimeError(f"Worker dependency missing: {package}; rebuild and recreate worker") from exc
                if installed != pinned:
                    raise RuntimeError(f"Worker dependency mismatch: {package}; rebuild and recreate worker")


if __name__ == "__main__":
    validate_worker_runtime()
    print("Worker runtime dependencies match the lockfile")
