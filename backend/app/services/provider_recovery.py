"""Safe rate-limit classification and bounded, durable provider deferrals."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
import re

from app.services.public_errors import ProviderRequestRejected

MAX_DEFERRALS = 2
MAX_AUTO_WAIT_SECONDS = 300


class ProviderRateLimited(ProviderRequestRejected):
    def __init__(self, scope='unknown', retry_after=None):
        self.scope = scope
        self.retry_after = retry_after
        self.can_retry = scope in {'upstream', 'rate'} or (scope == 'unknown' and retry_after is not None)
        code = 'PROVIDER_DAILY_LIMIT' if scope == 'daily' else 'PROVIDER_RATE_LIMIT'
        super().__init__(code + ': Provider request limit reached.')


def rate_limit_error(error):
    """Read only a completed error response; never expose provider bodies."""
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
    raw = (getattr(response, 'headers', None) or {}).get('retry-after')
    delay = None
    if raw:
        try:
            delay = float(raw)
        except (ValueError, TypeError):
            try:
                delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
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
    recovery = (config or {}).get('_provider_recovery') or {}
    count = recovery.get('count', 0) if recovery.get('run_id') == str(run_id) else 0
    return count < MAX_DEFERRALS and (error.retry_after or 60) <= MAX_AUTO_WAIT_SECONDS


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
    retry_at = now + timedelta(seconds=error.retry_after or 60)
    config['_provider_recovery'] = {'run_id': str(run.id), 'count': count}
    config['_provider_wait'] = {'reason': 'PROVIDER_RATE_LIMIT', 'retry_at': retry_at.isoformat(), 'retry_count': count}
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
    event.last_error = 'Provider temporarily rate limited; scheduled checkpoint resume'
    return True
