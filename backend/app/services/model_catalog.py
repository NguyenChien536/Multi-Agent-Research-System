"""Read public model metadata; never send a user's credential to the catalog."""
import time
import httpx

_cache = None
_expires = 0.0

async def free_models():
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
