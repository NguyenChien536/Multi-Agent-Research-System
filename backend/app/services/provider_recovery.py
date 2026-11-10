"""Safe rate-limit classification and durable provider deferrals."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
import re

from app.services.public_errors import ProviderRequestRejected, provider_http_status

MAX_AUTO_WAIT_SECONDS = 7 * 86400


class ProviderRateLimited(ProviderRequestRejected):
    def __init__(self, scope='unknown', retry_after=None):
        self.scope = scope
        self.retry_after = retry_after
        self.can_retry = scope in {'upstream', 'rate', 'unknown', 'daily'}
        code = 'PROVIDER_DAILY_LIMIT' if scope == 'daily' else 'PROVIDER_RATE_LIMIT'
        super().__init__(code + ': Provider request limit reached.')


def rate_limit_error(error):
    """Read only a completed error response; never expose provider bodies."""
    if provider_http_status(error) == 429:
        original = error
        for _ in range(4):
            direct = getattr(error, 'status_code', None) or getattr(getattr(error, 'response', None), 'status_code', None) or getattr(error, 'code', None)
            if str(direct) == '429':
                break
            nested = getattr(error, '__cause__', None) or getattr(error, '__context__', None)
            if nested is None:
                error = original
                break
            error = nested
    response = getattr(error, 'response', None)
    status = getattr(error, 'status_code', None) or getattr(response, 'status_code', None) or getattr(error, 'code', None)
    if str(status) != '429' and type(error).__name__ not in {'RateLimitError', 'GoogleRateLimitError'}:
        return None
    body = getattr(error, 'body', None)
    if not isinstance(body, dict) and response is not None:
        try:
            body = response.json()
        except (ValueError, TypeError, AttributeError):
            body = None
    body = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(body, dict):
        body = {}
    metadata = body.get('metadata') or {} if isinstance(body, dict) else {}
    source = metadata.get('limit_source', '') if isinstance(metadata, dict) else ''
    # Text is used for classification only, never stored or returned.
    text = (str(error) + ' ' + str(body.get('message', ''))).lower()
    daily = source in {'free_model_daily_requests', 'free_models_daily', 'daily'} or bool(
        re.search(r'per.day|daily|requests per day', text))
    scope = 'daily' if daily else 'upstream' if source in {'upstream_provider_shared_pool', 'upstream_provider', 'upstream'} else 'unknown'
    headers = getattr(response, 'headers', None) or {}
    raw = headers.get('retry-after')
    delay = None
    if raw:
        try:
            delay = float(raw)
        except (ValueError, TypeError):
            try:
                delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                pass
    elif headers.get('x-ratelimit-reset'):
        # OpenRouter sends this as Unix milliseconds for free-model quotas.
        # Accept seconds too for compatible OpenAI-style gateways.
        try:
            reset_at = float(headers['x-ratelimit-reset'])
            if reset_at >= 1_000_000_000_000:
                reset_at /= 1000
            delay = reset_at - datetime.now(timezone.utc).timestamp()
        except (ValueError, TypeError, OverflowError):
            pass
    if delay is not None and math.isfinite(delay):
        delay = max(1, math.ceil(delay))
        if scope == 'unknown':
            scope = 'rate'
    else:
        delay = None
    if scope == 'unknown' and re.search(r'temporar|retry shortly|per.minute|per.second', text):
        scope = 'upstream'
    return ProviderRateLimited(scope, delay)


def can_defer(error, config, run_id):
    if not isinstance(error, ProviderRateLimited) or not error.can_retry:
        return False
    # A provider's rate limit can persist across many scheduled attempts. Each
    # attempt releases its worker slot and writes one durable outbox schedule,
    # so retry count must not turn a recoverable 429 into a terminal failure.
    # A human can still cancel the task, and exceptionally long Retry-After
    # values are not shortened into an unsafe early retry.
    return (error.retry_after or 60) <= MAX_AUTO_WAIT_SECONDS


def retry_delay(error, count, *, now, base_url='', task_id=''):
    """Honor Retry-After; otherwise back off, or wait for a known daily reset."""
    if error.retry_after is not None:
        return max(1, min(error.retry_after, MAX_AUTO_WAIT_SECONDS))
    if error.scope == 'daily':
        if base_url == 'https://openrouter.ai/api/v1':
            reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
            return max(1, math.ceil((reset - now).total_seconds()))
        if base_url == 'https://generativelanguage.googleapis.com/v1beta/openai':
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                local = now.astimezone(ZoneInfo('America/Los_Angeles'))
                reset = (local + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
                return max(1, math.ceil((reset.astimezone(timezone.utc) - now).total_seconds()))
            except ZoneInfoNotFoundError:
                pass
        return 3600
    # Jitter is stable across restarts; never busy-loop or sleep inside a worker.
    import hashlib
    jitter = int(hashlib.sha256(str(task_id).encode()).hexdigest()[:4], 16) % 16
    return min(60 * (2 ** min(max(count - 1, 0), 6)), 3600) + jitter


async def schedule_provider_resume(session, task, run, error, now=None):
    """Reuse the same workflow and durable outbox; release worker/concurrency slot."""
    from sqlalchemy import select
    from app.models.task import TaskDispatchOutbox
    from app.services.provider_budget import pause_budget_config
    now = now or datetime.now(timezone.utc)
    if not can_defer(error, task.budget_config, run.id):
        return False
    config = pause_budget_config(task.budget_config, now=now)
    previous = config.get('_provider_recovery') or {}
    count = (previous.get('count', 0) if previous.get('run_id') == str(run.id) else 0) + 1
    from app.services.model_connection import current_connection
    connection = current_connection()
    root = connection.base_url if connection else ''
    delay = retry_delay(error, count, now=now, base_url=root, task_id=task.id)
    retry_at = now + timedelta(seconds=delay)
    config['_provider_recovery'] = {'run_id': str(run.id), 'count': count}
    reason = 'PROVIDER_DAILY_LIMIT' if error.scope == 'daily' else 'PROVIDER_RATE_LIMIT'
    config['_provider_wait'] = {'reason': reason, 'retry_at': retry_at.isoformat(), 'retry_count': count}
    task.budget_config = config
    task.status, task.completed_at, task.worker_lease_until = 'QUEUED', None, None
    task.queued_at = now
    run.status, run.completed_at, run.updated_at = 'RUNNING', None, now
    event = await session.scalar(select(TaskDispatchOutbox).where(
        TaskDispatchOutbox.research_task_id == task.id, TaskDispatchOutbox.event_type == 'START_RESEARCH').with_for_update())
    if event is None:
        event = TaskDispatchOutbox(research_task_id=task.id, event_type='START_RESEARCH')
        session.add(event)
    event.available_at, event.dispatched_at, event.locked_until = retry_at, None, None
    event.unclaimed_retries = 0
    event.last_error = 'Provider allowance unavailable; scheduled checkpoint resume'
    return True
