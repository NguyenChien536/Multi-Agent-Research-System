"""Readiness must fail closed without leaking dependency credentials."""
import json

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints import health
from app.core.config import Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("database,broker", [(True, True), (False, True), (True, False)])
async def test_readiness_dependency_failures(monkeypatch, database, broker):
    async def db():
        if not database:
            raise RuntimeError("postgres://private:secret@internal")
        return True

    async def redis():
        return broker

    monkeypatch.setattr(health, "_database_ready", db)
    monkeypatch.setattr(health, "_broker_ready", redis)
    response = await health.readiness_check()
    assert response.status_code == (200 if database and broker else 503)
    assert json.loads(response.body) == {
        "status": "ready" if database and broker else "unavailable",
        "database": database, "broker": broker,
    }
    assert b"secret" not in response.body
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("overrides", [{"DEBUG": True}, {"MOCK_PROVIDERS": True}])
def test_production_rejects_debug_and_mock(overrides):
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(_env_file=None, ENVIRONMENT="production", APP_SECRET_KEY="x" * 48,
                 **{"DEBUG": False, "MOCK_PROVIDERS": False, **overrides})


def test_production_accepts_real_provider_mode():
    settings = Settings(_env_file=None, ENVIRONMENT="production", APP_SECRET_KEY="x" * 48,
                        DEBUG=False, MOCK_PROVIDERS=False)
    assert not settings.DEBUG and not settings.MOCK_PROVIDERS
