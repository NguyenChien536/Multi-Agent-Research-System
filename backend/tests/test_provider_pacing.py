"""Exercise real Redis atomic reservations, not a reimplementation of the Lua."""
import asyncio
import os
import time
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.services import provider_pacing as pacing


@pytest_asyncio.fixture
async def redis_gate(monkeypatch):
    url = os.getenv('TEST_REDIS_URL')
    if not url:
        pytest.skip('Set TEST_REDIS_URL for the real-Redis pacing integration checks')
    key = 'test:provider-pacing:' + uuid.uuid4().hex
    monkeypatch.setattr(pacing, '_get_key', lambda model: key)
    monkeypatch.setattr(pacing, '_get_redis', lambda: Redis.from_url(url))
    async with Redis.from_url(url) as client:
        yield client, key
        # Only this test's UUID keys; never flush a shared Redis database.
        await client.delete(key, key + ':cooldown')


@pytest.mark.asyncio
async def test_atomic_slots_spread_concurrent_process_requests_and_reject_full_queue(redis_gate):
    redis, key = redis_gate
    delays = sorted(await asyncio.gather(*[redis.eval(pacing.RESERVE_LUA, 1, key, 100, 2000) for _ in range(8)]))
    assert delays[0] == 0
    assert all(b - a >= 80 for a, b in zip(delays, delays[1:])), delays
    previous = await redis.get(key)
    assert await redis.eval(pacing.RESERVE_LUA, 1, key, 100, 1) == -1
    assert await redis.get(key) == previous
    assert await redis.pttl(key) > 60000


@pytest.mark.asyncio
async def test_cooldown_does_not_shorten_existing_queue_or_retry_window(redis_gate):
    redis, key = redis_gate
    for _ in range(5):
        await redis.eval(pacing.RESERVE_LUA, 1, key, 100, 2000)
    previous = int(await redis.get(key))
    await redis.eval(pacing.COOLDOWN_LUA, 2, key, key + ':cooldown', 100)
    assert int(await redis.get(key)) >= previous
    await redis.eval(pacing.COOLDOWN_LUA, 2, key, key + ':cooldown', 400)
    await redis.eval(pacing.COOLDOWN_LUA, 2, key, key + ':cooldown', 10)
    assert await redis.pttl(key + ':cooldown') > 300


@pytest.mark.asyncio
async def test_already_waiting_calls_observe_new_429_without_a_thundering_herd(redis_gate, monkeypatch):
    redis, key = redis_gate
    monkeypatch.setattr(pacing.settings, 'GEMINI_REQUESTS_PER_MINUTE', 600)
    monkeypatch.setattr(pacing.settings, 'GEMINI_MAX_QUEUE_SECONDS', 2)
    await pacing.wait_for_gemini_slot('gemini-fixture')
    async def ready():
        await pacing.wait_for_gemini_slot('gemini-fixture')
        return time.monotonic()
    calls = [asyncio.create_task(ready()) for _ in range(2)]
    await asyncio.sleep(0.025)
    start = time.monotonic()
    await redis.eval(pacing.COOLDOWN_LUA, 2, key, key + ':cooldown', 300)
    times = sorted(await asyncio.gather(*calls))
    assert times[0] >= start + .27
    assert times[1] - times[0] >= .075


@pytest.mark.asyncio
async def test_full_queue_cannot_call_provider_or_reserve_its_budget(monkeypatch):
    from app.agents import nodes
    calls = []
    async def full(_):
        raise TimeoutError('queue full')
    async def unexpected(*args, **kwargs):
        calls.append('unexpected network or budget')
        raise AssertionError('Provider and budget must remain untouched')
    monkeypatch.setattr(pacing, 'wait_for_gemini_slot', full)
    monkeypatch.setattr(nodes, 'reserve_provider_call', unexpected)
    llm = nodes.BudgetedFallbackLLM([('gemini-fixture', SimpleNamespace(ainvoke=unexpected))], pace_requests=True)
    with pytest.raises(TimeoutError):
        await nodes.invoke_llm_with_budget({'task_id': str(uuid.uuid4()), 'enforce_provider_budget': True}, llm, [], model_name='gemini-fixture')
    assert calls == []


def test_cooldown_metadata_and_keys_are_bounded_without_exposing_the_api_key(monkeypatch):
    monkeypatch.setattr(pacing.settings, 'GEMINI_API_KEY', 'private-key-fixture')
    key = pacing._get_key('gemini-fixture')
    assert 'private-key-fixture' not in key
    assert pacing._extract_cooldown(Exception("retryDelay': '54s'")) == 54
    assert pacing._extract_cooldown(Exception('Please retry in 54.456s.')) == 55
    assert pacing._extract_cooldown(Exception('Unknown quota')) == 60
    assert pacing._extract_cooldown(Exception('retry in 9999s')) == 300
    assert pacing._extract_cooldown(Exception('retry in ' + '9' * 400 + 's')) == 300


@pytest.mark.asyncio
async def test_scheduler_oversleep_cannot_release_a_request_after_its_queue_deadline(monkeypatch):
    clock = [0.0]
    class RedisFixture:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def eval(self, *args): return 10
        async def pttl(self, *args): return -2
    async def oversleep(_): clock[0] += 3.0
    monkeypatch.setattr(pacing, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(pacing, 'asyncio', SimpleNamespace(sleep=oversleep))
    monkeypatch.setattr(pacing, '_get_redis', RedisFixture)
    monkeypatch.setattr(pacing.settings, 'GEMINI_MAX_QUEUE_SECONDS', 1)
    with pytest.raises(TimeoutError, match='deadline'):
        await pacing.wait_for_gemini_slot('gemini-fixture')


@pytest.mark.asyncio
async def test_version_question_route_cannot_bypass_the_shared_quota_gate(monkeypatch):
    from app.services import report_question_answering as answering
    touched = []
    async def full(_): raise TimeoutError('queue full')
    async def unexpected(*args, **kwargs): touched.append('unexpected budget or provider call')
    monkeypatch.setattr(answering, 'question_models', lambda: [('gemini-fixture', SimpleNamespace(ainvoke=unexpected))])
    monkeypatch.setattr(answering, 'wait_for_gemini_slot', full)
    monkeypatch.setattr(answering, 'reserve_provider_call', unexpected)
    with pytest.raises(TimeoutError):
        await answering.generate_answer(uuid.uuid4(), 1, uuid.uuid4(), 'What does this source support?', {})
    assert touched == []
