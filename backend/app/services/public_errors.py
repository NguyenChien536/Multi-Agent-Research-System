"""Public categories: never echo arbitrary exception bodies or credentials."""
class ProviderUnavailable(RuntimeError):
    """Configured providers exhausted their bounded retries for an upstream outage."""


def is_transient_provider_error(error):
    if error is None:
        return False
    status = getattr(error, 'status_code', getattr(error, 'code', None))
    if status in (502, 503, 504):
        return True
    value = str(error).lower()
    return any(marker in value for marker in ('503', '502', '504', 'high demand', 'overloaded'))


def public_error(raw):
    if not raw:
        return None
    value = raw.lower()
    cases = [
        (('insufficient_evidence',), 'INSUFFICIENT_EVIDENCE: Add relevant sources or recorded result data before writing a manuscript.'),
        (('lengthfinishreason', 'model_output_truncated'), 'MODEL_OUTPUT_TRUNCATED: Model output was cut off before completing JSON.'),
        (('provider_auth_failed', '401', 'unauthorized', 'invalid api key', 'api_key_invalid', 'permission_denied', '403'), 'PROVIDER_AUTH_FAILED: Provider rejected the key or access permission. Check the service and key permissions.'),
        (('503', '502', '504', 'unavailable', 'overloaded', 'high demand'), 'PROVIDER_UNAVAILABLE: The provider is temporarily overloaded or unavailable. Wait briefly and retry; this does not indicate an invalid API key.'),
        (('404', 'model_not_found', 'model was not found'), 'PROVIDER_MODEL_NOT_FOUND: The model is unavailable for this API connection. Reload the model list in Settings and choose an available chat model.'),
        (('provider_rate_limit', '429', 'quota', 'rate limit', 'request queue'), 'PROVIDER_RATE_LIMIT: Provider quota or rate limit reached.'),
        (('timeout', 'timed out'), 'PROVIDER_TIMEOUT: Provider response timed out.'),
        (('budget',), 'TASK_BUDGET_LIMIT: Task allowance reached.'),
        (('json', 'outputparser'), 'MODEL_INVALID_JSON: Model returned invalid structured data.'),
    ]
    # Reclassification of a stored safe message must preserve its category;
    # explanatory text can mention another error (e.g. "not an invalid key").
    for _, message in cases:
        if value.startswith(message.split(':', 1)[0].lower() + ':'):
            return message
    for markers, message in cases:
        if any(marker in value for marker in markers):
            return message
    return 'EXECUTION_FAILED: This step could not finish. Review the monitor before retrying.'
