"""Public categories: never echo arbitrary exception bodies or credentials."""
class ProviderUnavailable(RuntimeError):
    """Configured providers exhausted their bounded retries for an upstream outage."""


class ProviderRequestRejected(RuntimeError):
    """The provider explicitly rejected authentication, access, model or quota."""


class ProviderResponseTimeout(TimeoutError):
    """A timeout at the provider boundary, distinct from unrelated workflow bugs."""


def provider_request_rejected(error):
    """Only explicit HTTP rejection statuses, never message substrings/timeouts.

    These responses contain no generated completion. Keep the attempted call in
    the ledger, but do not charge a hypothetical full output-token reservation.
    Unknown failures and upstream 5xx remain conservatively reserved.
    """
    status = getattr(error, 'status_code', getattr(error, 'code', None))
    if status is None:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
    return str(status) in ('401', '403', '404', '429') or type(error).__name__ in ('GoogleRateLimitError', 'RateLimitError')


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
        (('manuscript_incomplete',), 'MANUSCRIPT_INCOMPLETE: A writing section is incomplete. Saved sections are retained; continue from the failed step.'),
        (('provider_daily_limit',), 'PROVIDER_DAILY_LIMIT: Provider daily request allowance reached. Wait for its reset or choose another configured service.'),
        (('workflow_resume_conflict', 'invalid_concurrent_graph_update', 'can receive only one value per step'), 'WORKFLOW_RESUME_CONFLICT: The saved workflow could not resume safely. Previous results are retained; refresh and retry after the workflow fix is deployed.'),
        (('insufficient_evidence',), 'INSUFFICIENT_EVIDENCE: Add relevant sources or recorded result data before writing a manuscript.'),
        (('lengthfinishreason', 'model_output_truncated'), 'MODEL_OUTPUT_TRUNCATED: Model output was cut off before completing JSON.'),
        (('provider_auth_failed', '401', 'unauthorized', 'invalid api key', 'api_key_invalid', 'permission_denied', '403'), 'PROVIDER_AUTH_FAILED: Provider rejected the key or access permission. Check the service and key permissions.'),
        (('503', '502', '504', 'unavailable', 'overloaded', 'high demand'), 'PROVIDER_UNAVAILABLE: The provider is temporarily overloaded or unavailable. Wait briefly and retry; this does not indicate an invalid API key.'),
        (('404', 'model_not_found', 'model was not found'), 'PROVIDER_MODEL_NOT_FOUND: The model is unavailable for this API connection. Reload the model list in Settings and choose an available chat model.'),
        (('provider_rate_limit', '429', 'quota', 'rate limit', 'request queue'), 'PROVIDER_RATE_LIMIT: Provider quota or rate limit reached.'),
        (('task_time_limit', 'active research time budget'), 'TASK_TIME_LIMIT: Research active-time allowance is exhausted. Saved work is retained; increasing output tokens does not extend this limit.'),
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


async def task_error_summary(db, task):
    """One safe current failure for workspace and monitor, including legacy null errors."""
    if task.status != 'FAILED' and not (task.status == 'NEEDS_REVIEW' and task.current_step == 'BUDGET_LIMIT'):
        return None, None
    from sqlalchemy import select
    from app.models.agent_run import AgentRun
    from app.services.provider_budget import pause_budget_config, _limits
    config = pause_budget_config(task.budget_config, now=task.completed_at)
    saved = config.get('_last_failure') or {}
    current = saved.get('attempt_number') == task.attempt_number
    step = (saved.get('step') or task.current_step) if current else task.current_step
    # Older asyncio deadline exceptions had an empty string. The retained
    # ledger can identify exhausted active time without rewriting that history.
    if (config.get('_provider_usage') or {}).get('active_seconds', 0) >= _limits(config)[4]:
        return public_error('TASK_TIME_LIMIT:'), step
    failure = await db.scalar(select(AgentRun).where(AgentRun.research_task_id == task.id,
        AgentRun.attempt_number == task.attempt_number, AgentRun.status == 'FAILED')
        .order_by(AgentRun.started_at.desc()).limit(1))
    if failure and failure.error_message:
        return public_error(failure.error_message), failure.agent_name
    if current and saved.get('message'):
        return public_error(saved['message']), step
    return public_error('budget' if task.current_step == 'BUDGET_LIMIT' else 'unknown execution error'), step
