import asyncio
import pytest
from app.core.database import engine


@pytest.fixture(autouse=True)
def cleanup_db_engine():
    yield
    try:
        asyncio.run(engine.dispose())
    except Exception:
        pass
