"""Task-scoped, encrypted connections to OpenAI-compatible chat APIs.

Secrets never enter graph state, model traces, browser persistence or responses.
The server operator controls trusted API roots; this is not a general URL proxy.
"""
import base64
import contextvars
import hashlib
import json
import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from typing import Literal, Annotated

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.core.config import settings


def validate_api_root(value: str) -> str:
    root = value.strip().rstrip("/")
    parts = urlsplit(root)
    allowed = {item.strip().rstrip("/") for item in settings.CUSTOM_LLM_API_ROOTS.split(",") if item.strip()}
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.port not in (None, 443) or root not in allowed):
        raise ValueError("Choose a trusted HTTPS API base URL configured by the server administrator")
    return root


class ModelConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    api_key: SecretStr = Field(min_length=8, max_length=4096, repr=False)
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/@+\-]*$")
    # Account-specific prices are estimates declared by the owner, not an invoice.
    input_price_per_million: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    output_price_per_million: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    output_token_limit: int = Field(default=32768, ge=1024, le=1_000_000)
    reasoning_effort: Literal['none', 'low', 'medium', 'high'] = 'low'
    structured_output_mode: Literal['json_object', 'json_schema', 'prompt_json'] = 'json_object'
    fallback_models: list[Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/@+\-]*$')]] = Field(default_factory=list, max_length=3)

    @field_validator("base_url")
    @classmethod
    def trusted_root(cls, value):
        return validate_api_root(value)

    @field_validator("api_key")
    @classmethod
    def valid_secret(cls, value):
        secret = value.get_secret_value()
        if secret != secret.strip() or any(ord(c) < 33 or ord(c) > 126 for c in secret):
            raise ValueError("API key must contain printable characters without whitespace")
        return value

    @model_validator(mode="after")
    def free_openrouter_model(self):
        if self.fallback_models:
            if self.base_url != 'https://openrouter.ai/api/v1' or not self.is_zero_price:
                raise ValueError('Model fallbacks are available only for zero-price OpenRouter connections')
            if any(not name.endswith(':free') for name in self.fallback_models):
                raise ValueError('Choose only explicit :free fallback models')
            self.fallback_models = list(dict.fromkeys(name for name in self.fallback_models if name != self.model))
        if self.base_url == "https://openrouter.ai/api/v1" and self.is_zero_price:
            if not (self.model.endswith(":free") or self.model == "openrouter/free"):
                raise ValueError("For zero-price OpenRouter connections, select a :free model or openrouter/free")
        return self

    @property
    def is_zero_price(self):
        return self.input_price_per_million == 0 and self.output_price_per_million == 0


INSECURE_APP_SECRETS = {
    "development-secret-key-replace-in-production-32-chars-min",
    "replace-with-a-secure-random-secret-key-32-chars-min",
    "change-me",
    "secret",
}


@dataclass
class ModelConnection:
    base_url: str
    model: str
    input_price_per_million: float
    output_price_per_million: float
    api_key: str = field(repr=False)
    output_token_limit: int = 32768
    reasoning_effort: str = 'low'
    structured_output_mode: str = 'json_object'
    fallback_models: list[str] = field(default_factory=list)
    last_response_model: str | None = field(default=None, init=False, repr=False)
    _clients: list = field(default_factory=list, repr=False)

    @property
    def model_tag(self):
        return "byok:" + self.model

    def estimate(self, input_tokens, output_tokens):
        return round((max(0, input_tokens) * self.input_price_per_million
                      + max(0, output_tokens) * self.output_price_per_million) / 1_000_000, 8)

    def register_client(self, client):
        self._clients.append(client)
        return client

    async def aclose(self):
        clients, self._clients = self._clients, []
        pending = []
        for client in clients:
            if getattr(client, "http_client", None):
                client.http_client.close()
            if getattr(client, "http_async_client", None):
                pending.append(client.http_async_client.aclose())
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def close(self):
        for client in self._clients:
            try:
                if hasattr(client, "http_client") and client.http_client:
                    client.http_client.close()
            except Exception:
                pass
            try:
                if hasattr(client, "http_async_client") and client.http_async_client:
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(client.http_async_client.aclose())
                    except RuntimeError:
                        pass
            except Exception:
                pass
        self._clients.clear()


_connection: contextvars.ContextVar[ModelConnection | None] = contextvars.ContextVar("task_model_connection", default=None)


def current_connection():
    return _connection.get()


@asynccontextmanager
async def temporary_connection_scope(connection):
    """Use an owner-authorized Settings probe without persisting credentials."""
    token = _connection.set(connection)
    try:
        yield connection
    finally:
        try:
            await connection.aclose()
        finally:
            _connection.reset(token)


def _cipher():
    key = hashlib.sha256(("synthia/task-model/v1\0" + settings.APP_SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal_connection(value: ModelConnectionInput, task_id, user_id) -> dict:
    if (settings.APP_SECRET_KEY in INSECURE_APP_SECRETS or len(settings.APP_SECRET_KEY) < 32) and not settings.MOCK_PROVIDERS:
        raise ValueError("Cannot protect personal API credentials using a default server secret; update APP_SECRET_KEY first")
    profile = value.model_dump(exclude={"api_key"})
    payload = {**profile, "api_key": value.api_key.get_secret_value(), "task_id": str(task_id), "user_id": str(user_id)}
    return {"profile": profile, "secret": _cipher().encrypt(json.dumps(payload).encode()).decode()}


def open_connection(config: dict | None, task_id, user_id) -> ModelConnection | None:
    # A personal connection always takes precedence. Server mode supplies the
    # default only when the article has no personal connection; never silently
    # spend server credits after a user's connection fails.
    stored = (config or {}).get("_llm_connection")
    if stored is None:
        return None
    try:
        if stored.get("revoked"):
            raise ValueError("revoked")
        payload = json.loads(_cipher().decrypt(stored["secret"].encode()))
        if payload.pop("task_id") != str(task_id) or payload.pop("user_id") != str(user_id):
            raise ValueError("owner mismatch")
        # Older encrypted snapshots omitted this field and used 8192. Keep
        # historical tasks reproducible rather than upgrading them on read.
        payload.setdefault('output_token_limit', 8192)
        validated = ModelConnectionInput.model_validate(payload)
        profile_values = {**stored['profile']}
        profile_values.setdefault('output_token_limit', 8192)
        profile = ModelConnectionInput(api_key=validated.api_key, **profile_values)
        if validated.model_dump(exclude={"api_key"}) != profile.model_dump(exclude={'api_key'}):
            raise ValueError("profile mismatch")
        return ModelConnection(**validated.model_dump(exclude={"api_key"}), api_key=validated.api_key.get_secret_value())
    except (InvalidToken, KeyError, TypeError, ValueError):
        # Do not include either input or provider exception text in a public error.
        raise ValueError("The research API connection is unavailable; configure it again before continuing") from None


def activate_connection(config, task_id, user_id):
    return _connection.set(open_connection(config, task_id, user_id))


def reset_connection(token):
    conn = _connection.get()
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _connection.reset(token)


async def reset_connection_async(token):
    conn = _connection.get()
    try:
        if conn is not None:
            await conn.aclose()
    finally:
        _connection.reset(token)


@asynccontextmanager
async def async_connection_scope(config, task_id, user_id):
    token = activate_connection(config, task_id, user_id)
    try:
        yield
    finally:
        await reset_connection_async(token)


@contextmanager
def connection_scope(config, task_id, user_id):
    conn = open_connection(config, task_id, user_id)
    token = _connection.set(conn)
    try:
        yield
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _connection.reset(token)


def build_connection_client(connection: ModelConnection):
    import httpx
    from langchain_openai import ChatOpenAI
    extra = {}
    if connection.base_url == "https://openrouter.ai/api/v1":
        # The free router can select models with mandatory reasoning. Request
        # low effort rather than disabling it; exclusion only hides the trace.
        extra["reasoning"] = ({"enabled": False} if connection.reasoning_effort == 'none' else {"effort": connection.reasoning_effort, "exclude": True})
        extra['provider'] = {'require_parameters': True}
        if getattr(connection, 'fallback_models', None):
            # OpenRouter performs ordered failover inside the same owner-key
            # request. The zero-price restriction below still applies to all.
            extra['models'] = list(connection.fallback_models)
            extra['route'] = 'fallback'
    if connection.base_url == "https://openrouter.ai/api/v1" and connection.input_price_per_million == 0 and connection.output_price_per_million == 0:
        extra['provider']['max_price'] = {"prompt": 0, "completion": 0, "request": 0}
    if connection.base_url == 'https://generativelanguage.googleapis.com/v1beta/openai' and connection.model.startswith('gemini-'):
        # Gemini 3 reasoning cannot be disabled. Its compatibility API accepts
        # low/medium/high; an omitted setting can use expensive default thinking.
        extra['reasoning_effort'] = 'low' if connection.reasoning_effort == 'none' else connection.reasoning_effort
    # No environment key, global cache, redirect or provider fallback is used.
    client = ChatOpenAI(model=connection.model, api_key=connection.api_key, base_url=connection.base_url,
        max_retries=0, timeout=settings.PROVIDER_CALL_TIMEOUT_SECONDS, cache=False,
        max_tokens=connection.output_token_limit, extra_body=extra, callbacks=[],
        http_client=httpx.Client(follow_redirects=False, trust_env=False),
        http_async_client=httpx.AsyncClient(follow_redirects=False, trust_env=False))
    if hasattr(connection, "register_client"):
        connection.register_client(client)
    return client


def remember_response_model(response):
    """Keep only bounded model metadata, never private generated content."""
    import re
    connection = current_connection()
    if not connection or not getattr(connection, 'fallback_models', None):
        return
    metadata = getattr(response, 'response_metadata', None) or {}
    model = metadata.get('model_name') or metadata.get('model')
    allowed = {name.removesuffix(':free') for name in [connection.model, *connection.fallback_models]}
    valid = isinstance(model, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/@+\-]{0,199}', model)
    connection.last_response_model = model if valid and model.removesuffix(':free') in allowed else None


def route_json_retry(client, response):
    """One local format retry may use an explicitly selected free backup."""
    connection = current_connection()
    if not connection or not getattr(connection, 'fallback_models', None) or not hasattr(client, 'model_name'):
        return
    metadata = getattr(response, 'response_metadata', None) or {}
    failed = metadata.get('model_name') or getattr(client, 'model_name', connection.model)
    candidates = [name for name in connection.fallback_models
                  if name.removesuffix(':free') != str(failed).removesuffix(':free')]
    if not candidates:
        return
    selected = candidates[0]
    client.model_name = selected
    # Structured bindings share this list with the original transport body.
    backups = client.extra_body.get('models')
    if isinstance(backups, list):
        backups[:] = [name for name in [connection.model, *connection.fallback_models] if name != selected]
