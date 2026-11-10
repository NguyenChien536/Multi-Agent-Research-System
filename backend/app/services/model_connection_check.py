"""Bounded owner-key checks. Metadata checks never generate; probes make one call."""
import asyncio
import json
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.services.model_connection import ModelConnection, ModelConnectionInput, build_connection_client, temporary_connection_scope
from app.services.model_catalog import discover_models


class ProbeFinding(BaseModel):
    step: Literal['evidence', 'writing', 'review']
    supported: bool
    note: str = Field(max_length=120)


class WorkflowConnectionProbe(BaseModel):
    """Exercise nested records, enums and arrays used by real agent schemas."""
    ok: Literal[True]
    findings: list[ProbeFinding] = Field(min_length=1, max_length=2)


async def check_connection(value: ModelConnectionInput, *, generate: bool = False, free_tier_confirmed: bool = False,
                           paid_probe_confirmed: bool = False) -> dict:
    result = {'model': value.model, 'generation_calls': 0,
              'checked_at': datetime.now(timezone.utc).isoformat()}
    root, key = value.base_url, value.api_key.get_secret_value()
    try:
        if root == 'https://openrouter.ai/api/v1':
            async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
                async with client.stream('GET', root+'/key', headers={'Authorization':'Bearer '+key}) as response:
                    response.raise_for_status()
                    data, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 256*1024:
                            return {**result, 'status':'invalid_metadata'}
                        data.append(chunk)
            payload = json.loads(b''.join(data))
            meta = payload.get('data') if isinstance(payload, dict) else None
            if not isinstance(meta, dict):
                return {**result, 'status':'invalid_metadata'}
            quota = meta.get('free_model_daily_requests')
            if isinstance(quota, dict) and all(isinstance(quota.get(k), int) and not isinstance(quota[k], bool) for k in ('used','limit','remaining')):
                result['quota'] = {k:max(0, quota[k]) for k in ('used','limit','remaining')}
                if value.is_zero_price and quota['remaining'] <= 0:
                    return {**result, 'status':'quota_exhausted'}
        try:
            catalog = await discover_models(root,key,free_only=value.is_zero_price)
            available = {m['id'] for m in catalog['models']}
            if not available.intersection([value.model, *value.fallback_models]):
                return {**result, 'status':'model_unavailable'}
            result['primary_model_available'] = value.model in available
        except HTTPException as exc:
            if not (generate and 'MODEL_CATALOG_UNAVAILABLE' in str(exc.detail)):
                detail = str(exc.detail)
                status = next((name for code, name in (
                    ('PROVIDER_AUTH_FAILED', 'auth_failed'),
                    ('PROVIDER_RATE_LIMIT', 'rate_limited'),
                    ('PROVIDER_TIMEOUT', 'timeout'),
                    ('PROVIDER_UNAVAILABLE', 'unavailable'),
                ) if code in detail), 'catalog_unavailable')
                return {**result, 'status': status}
        if not generate:
            return {**result, 'status':'catalog_ok'}
        if not value.is_zero_price and not paid_probe_confirmed:
            return {**result, 'status':'paid_probe_confirmation_required'}
        if value.is_zero_price and root != 'https://openrouter.ai/api/v1' and not free_tier_confirmed:
            return {**result, 'status':'free_tier_confirmation_required'}
        connection = ModelConnection(**value.model_dump(exclude={'api_key'}), api_key=key)
        connection.output_token_limit = min(connection.output_token_limit,2048)
        from langchain_core.messages import HumanMessage
        from langsmith import tracing_context
        from app.services.structured_output import compatible_structured_output
        async with temporary_connection_scope(connection):
            model = compatible_structured_output(connection.model_tag,build_connection_client(connection),WorkflowConnectionProbe)
            result['generation_calls'] = 1
            async with asyncio.timeout(45):
                with tracing_context(enabled=False):
                    response = await model.ainvoke([HumanMessage(content='Return exactly {"ok":true,"findings":[{"step":"review","supported":true,"note":"Connection test only; no research evaluated."}]} without extra commentary.')])
            return {**result, 'status':'ok' if response.ok else 'invalid_output',
                    'scope':'small_json_response_not_full_research'}
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        return {**result,'status':{401:'auth_failed',403:'access_denied',404:'model_unavailable',429:'rate_limited'}.get(code,'unavailable')}
    except (TimeoutError,httpx.TimeoutException):
        return {**result,'status':'timeout'}
    except Exception as exc:
        from app.services.provider_recovery import rate_limit_error
        from app.services.structured_output import StructuredOutputFailure
        if limited := rate_limit_error(exc):
            return {**result,'status':'quota_exhausted' if limited.scope=='daily' else 'rate_limited'}
        from app.services.public_errors import provider_http_status, provider_failure_message
        code=provider_http_status(exc)
        status={400:'unsupported_format',401:'auth_failed',403:'access_denied',404:'model_unavailable',429:'rate_limited'}.get(code)
        if not status and (provider_failure_message(exc) or '').startswith('PROVIDER_REQUEST_INVALID:'):
            status='unsupported_format'
        if not status and isinstance(exc,StructuredOutputFailure):
            status='incomplete_output' if str(exc).startswith('MODEL_OUTPUT_TRUNCATED') else 'invalid_output'
        return {**result,'status':status or 'unavailable'}
