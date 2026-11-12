import asyncio
import os
import re
from urllib.parse import unquote, urlsplit, urlunsplit

import pytest


test_database_url = os.environ.get("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError(
        "Refusing to run backend tests without TEST_DATABASE_URL. "
        "Use a disposable PostgreSQL database whose name contains 'test'; "
        "never point tests at the development database."
    )

parsed_test_url = urlsplit(test_database_url)
test_database_name = unquote(parsed_test_url.path.rstrip("/").split("/")[-1])
if not re.search(r"(^|[_-])test([_-]|$)", test_database_name, flags=re.IGNORECASE):
    raise RuntimeError(
        "TEST_DATABASE_URL must point to a disposable database whose name contains 'test'."
    )

# Make the application's async and sync database settings use the same isolated
# test database before importing any app modules that create an engine.
os.environ["DATABASE_URL"] = test_database_url
test_sync_database_url = os.environ.get("TEST_POSTGRES_SYNC_URL")
if not test_sync_database_url:
    test_sync_database_url = urlunsplit(
        (
            parsed_test_url.scheme.replace("+asyncpg", ""),
            parsed_test_url.netloc,
            parsed_test_url.path,
            parsed_test_url.query,
            parsed_test_url.fragment,
        )
    )
parsed_sync_url = urlsplit(test_sync_database_url)
sync_database_name = unquote(parsed_sync_url.path.rstrip("/").split("/")[-1])
if (
    sync_database_name != test_database_name
    or parsed_sync_url.hostname != parsed_test_url.hostname
    or parsed_sync_url.port != parsed_test_url.port
    or parsed_sync_url.username != parsed_test_url.username
):
    raise RuntimeError(
        "TEST_POSTGRES_SYNC_URL must target the same test database and server "
        "as TEST_DATABASE_URL."
    )
os.environ["POSTGRES_SYNC_URL"] = test_sync_database_url

from app.core.database import engine


@pytest.fixture(autouse=True)
def cleanup_db_engine():
    yield
    try:
        asyncio.run(engine.dispose())
    except Exception:
        pass
