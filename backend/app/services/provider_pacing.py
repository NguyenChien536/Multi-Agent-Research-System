"""Cross-process request pacing; waiting never makes a provider call or spends tokens."""
import asyncio
import hashlib
import math
import re
import time
from typing import Any
import redis.asyncio as aioredis
from app.core.config import settings

RESERVE_LUA = """
local key = KEYS[1]
local interval = tonumber(ARGV[1])
local max_wait = tonumber(ARGV[2])
local t = redis.call('TIME')
local now = math.floor(tonumber(t[1]) * 1000 + tonumber(t[2]) / 1000)
local next_slot = tonumber(redis.call('GET', key) or 0)
local delay = math.max(0, next_slot - now)
if delay > max_wait then return -1 end
local base = math.max(now, next_slot)
local new_slot = base + interval
local ttl = math.ceil(delay + interval + 60000)
redis.call('PSETEX', key, ttl, string.format('%.0f', new_slot))
return delay
"""

COOLDOWN_LUA = """
local key = KEYS[1]
local cooldown = tonumber(ARGV[1])
local t = redis.call('TIME')
local now = math.floor(tonumber(t[1]) * 1000 + tonumber(t[2]) / 1000)
local target = now + cooldown
local old_cooldown = redis.call('PTTL', KEYS[2])
cooldown = math.max(cooldown, old_cooldown)
target = now + cooldown
redis.call('PSETEX', KEYS[2], cooldown, '1')
local current = tonumber(redis.call('GET', key) or 0)
local new_slot = math.max(current, target)
local ttl = math.max(math.ceil(cooldown + 60000), math.ceil(new_slot - now + 60000))
redis.call('PSETEX', key, ttl, string.format('%.0f', new_slot))
return new_slot
"""

reserve_lua = RESERVE_LUA
cooldown_lua = COOLDOWN_LUA


def _get_key(model: str) -> str:
    key_src = (getattr(settings, "GEMINI_API_KEY", "") or "").encode("utf-8")
    key_hash = hashlib.sha256(key_src).hexdigest()[:16]
    safe_model = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", model)
    return f"provider:pace:gemini:{key_hash}:{safe_model}"


def _get_redis() -> aioredis.Redis:
    return aioredis.Redis.from_url(
        settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=3
    )


async def wait_for_gemini_slot(model: str) -> None:
    if not model.startswith("gemini-"):
        return
    rpm = int(getattr(settings, "GEMINI_REQUESTS_PER_MINUTE", 12))
    interval_ms = math.ceil(60000 / max(1, rpm))
    max_wait_ms = int(getattr(settings, "GEMINI_MAX_QUEUE_SECONDS", 90)) * 1000
    deadline = time.monotonic() + max_wait_ms / 1000
    key = _get_key(model)
    async with _get_redis() as r:
        while True:
            remaining = math.floor((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise TimeoutError("Gemini request queue deadline reached before provider call")
            delay = await r.eval(RESERVE_LUA, 1, key, interval_ms, remaining)
            if delay == -1:
                raise TimeoutError("Gemini request queue is full; no provider call made")
            if delay > 0:
                await asyncio.sleep(delay / 1000.0)
            # A 429 arriving while we slept invalidates the old slot. Reserve a
            # new spaced slot after cooldown rather than releasing all waiters together.
            if await r.pttl(key + ':cooldown') <= 0:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Gemini request queue deadline reached before provider call")
                return


def _extract_cooldown(exc: Any) -> int:
    txt = str(exc)
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s?", txt, re.I) or \
        re.search(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", txt, re.I)
    val = float(m.group(1)) if m else 60.0
    return math.ceil(max(1, min(300, val)))


async def record_gemini_rate_limit(model: str, exc: Any) -> None:
    if not model.startswith("gemini-"):
        return
    name = exc.__class__.__name__
    status = getattr(exc, "status_code", getattr(exc, "code", None))
    if name not in ("GoogleRateLimitError", "RateLimitError") and status != 429:
        return
    cooldown_ms = _extract_cooldown(exc) * 1000
    key = _get_key(model)
    async with _get_redis() as r:
        await r.eval(COOLDOWN_LUA, 2, key, key + ':cooldown', cooldown_ms)
