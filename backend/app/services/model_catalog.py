"""Read the selected provider's catalog without generating or billing chat tokens."""
import json
import re
import time

import httpx
from fastapi import HTTPException

from app.services.model_connection import validate_api_root
from app.services.public_errors import public_error

MODEL_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:/@+\-]{0,199}$')
_cache = None
_expires = 0.0


async def free_models():
    """Public OpenRouter metadata; never use personal credentials for this cache."""
    global _cache, _expires
    if _cache is not None and time.monotonic() < _expires:
        return _cache
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        response = await client.get('https://openrouter.ai/api/v1/models')
        response.raise_for_status()
        values = response.json().get('data', [])
    result = []
    for model in values:
        price = model.get('pricing') or {}
        try:
            zero = float(price.get('prompt', -1)) == float(price.get('completion', -1)) == 0
        except (ValueError, TypeError):
            continue
        if zero and model.get('id', '').endswith(':free') and 'response_format' in model.get('supported_parameters', []):
            result.append({'id': model['id'], 'context_length': model.get('context_length'),
                           'max_output_tokens': (model.get('top_provider') or {}).get('max_completion_tokens')})
    _cache, _expires = result[:100], time.monotonic() + 300
    return _cache


async def discover_models(base_url: str, api_key: str, free_only: bool = True):
    root = validate_api_root(base_url)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
            async with client.stream('GET', root + '/models', headers={'Authorization': 'Bearer ' + api_key}) as response:
                if response.status_code != 200:
                    # Never forward provider bodies, request headers or secret-bearing URLs.
                    code = response.status_code
                    if code in (401, 403):
                        raise HTTPException(400, 'PROVIDER_AUTH_FAILED: This service rejected the API key or its permissions.')
                    if code in (404, 405):
                        raise HTTPException(400, 'MODEL_CATALOG_UNAVAILABLE: This service does not provide a model list here. Enter its exact chat model ID manually.')
                    raise HTTPException(503, public_error(str(code)))
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise HTTPException(502, 'MODEL_CATALOG_UNAVAILABLE: Model list exceeded the supported size.')
                    chunks.append(chunk)
        payload = json.loads(b''.join(chunks))
    except httpx.TimeoutException:
        raise HTTPException(504, 'PROVIDER_TIMEOUT: Loading the model list timed out. Try again.') from None
    except httpx.HTTPError:
        raise HTTPException(502, 'PROVIDER_UNAVAILABLE: Could not connect to the selected API service.') from None
    except (ValueError, TypeError):
        raise HTTPException(502, 'MODEL_CATALOG_UNAVAILABLE: The service returned an invalid model list.') from None
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise HTTPException(502, 'MODEL_CATALOG_UNAVAILABLE: The service returned an unsupported model list.')
    models = {}
    for item in payload['data']:
        if not isinstance(item, dict):
            continue
        name = item.get('id')
        if isinstance(name, str) and root == 'https://generativelanguage.googleapis.com/v1beta/openai':
            # Google's compatibility catalog returns resource names; completion
            # requests and Settings use the model ID, without the models/ prefix.
            name = name.removeprefix('models/')
            if not name.startswith(('gemini-', 'gemma-')):
                continue
            if any(word in name for word in ('-live', 'computer-use', 'robotics', 'nano-banana', 'customtools')):
                continue
        if not isinstance(name, str) or not MODEL_ID.fullmatch(name) or api_key in name:
            continue
        architecture = item.get('architecture')
        output = architecture.get('output_modalities') if isinstance(architecture, dict) else None
        if isinstance(output, list) and 'text' not in output:
            continue
        if any(word in name.lower() for word in ('embedding', 'whisper', 'tts', 'transcribe', 'image', 'moderation', 'realtime', 'audio', 'dall-e', 'sora', 'video')):
            continue
        pricing = item.get('pricing') if isinstance(item.get('pricing'), dict) else {}
        free = bool(pricing) and all(str(pricing.get(key, '')) in ('0', '0.0') for key in ('prompt', 'completion'))
        if root == 'https://openrouter.ai/api/v1' and free_only:
            if not (free and name.endswith(':free')):
                continue
        models[name] = {'id': name, 'free': free if pricing else None}
    if root == 'https://openrouter.ai/api/v1' and free_only:
        models['openrouter/free'] = {'id': 'openrouter/free', 'free': True}
    if not models:
        raise HTTPException(400, 'MODEL_CATALOG_UNAVAILABLE: No matching text models were found. Check the API service and account permissions.')
    return {'models': [models[key] for key in sorted(models)[:500]],
            'check': 'catalog_only_not_generation_or_quota', 'generation_calls': 0}
