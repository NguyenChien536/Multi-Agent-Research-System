"""Public categories: never echo arbitrary exception bodies or credentials."""
def public_error(raw):
    if not raw:
        return None
    value = raw.lower()
    for markers, message in [
        (('lengthfinishreason', 'model_output_truncated'), 'MODEL_OUTPUT_TRUNCATED: Model output was cut off before completing JSON.'),
        (('401', 'unauthorized'), 'PROVIDER_AUTH_FAILED: Provider rejected authentication.'),
        (('429', 'quota', 'rate limit'), 'PROVIDER_RATE_LIMIT: Provider quota or rate limit reached.'),
        (('timeout', 'timed out'), 'PROVIDER_TIMEOUT: Provider response timed out.'),
        (('budget',), 'TASK_BUDGET_LIMIT: Task allowance reached.'),
        (('json', 'outputparser'), 'MODEL_INVALID_JSON: Model returned invalid structured data.'),
    ]:
        if any(marker in value for marker in markers):
            return message
    return 'EXECUTION_FAILED: This step could not finish. Review the monitor before retrying.'
