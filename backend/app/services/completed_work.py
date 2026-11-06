"""Persist completed units within one owner's workflow and exact model/input scope."""
import hashlib
import json
import uuid
from types import SimpleNamespace
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, WorkflowRun
from app.models.user import User
from app.models.provider_result import ProviderResult
from app.services.provider_budget import ResearchTaskStopped
from app.services.model_connection import current_connection


class CompletedWork:
    def __init__(self, state, connection):
        self.task_id = uuid.UUID(state['task_id'])
        self.run_id = uuid.UUID(state['workflow_run_id'])
        self.attempt = state['attempt_number']
        self.connection = connection

    @classmethod
    def for_state(cls, state):
        from app.core.runtime import current_runtime
        if current_runtime() is not None:
            return None  # Evaluation runs must measure real attempts, not cache reuse.
        connection = current_connection()
        if state.get('enforce_provider_budget') and state.get('task_id') and state.get('workflow_run_id'):
            if connection is None:
                from app.core.config import settings
                connection = SimpleNamespace(base_url='server:' + settings.LLM_PROVIDER_PRIORITY,
                    model=settings.LLM_PROVIDER_PRIORITY, output_token_limit=0, reasoning_effort='configured',
                    structured_output_mode='native', api_key='\0'.join(str(getattr(settings, key, '') or '')
                        for key in ('GEMINI_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','GROQ_API_KEY')))
            return cls(state, connection)
        return None

    def fingerprint(self, value):
        # The key participates only in a digest; it is never stored in payloads.
        config = {'root': self.connection.base_url, 'model': self.connection.model,
                  'capacity': self.connection.output_token_limit, 'reasoning': self.connection.reasoning_effort,
                  'format': self.connection.structured_output_mode}
        raw = json.dumps([config, value], sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256((self.connection.api_key + '\0' + raw).encode()).hexdigest()

    async def _claim(self, db):
        task = await db.scalar(select(ResearchTask).join(User).join(WorkflowRun, WorkflowRun.research_task_id == ResearchTask.id).where(
            ResearchTask.id == self.task_id, WorkflowRun.id == self.run_id,
            WorkflowRun.status == 'RUNNING',
            ResearchTask.status == 'RUNNING', ResearchTask.attempt_number == self.attempt,
            User.deleted_at.is_(None)).with_for_update(of=ResearchTask))
        if task is None or (task.worker_lease_until and task.worker_lease_until <= datetime.now(timezone.utc)):
            raise ResearchTaskStopped('Saved work is unavailable for this workflow claim')
        return task

    async def load(self, operation, digest):
        async with AsyncSessionLocal() as db:
            await self._claim(db)
            row = await db.scalar(select(ProviderResult).where(ProviderResult.research_task_id == self.task_id,
                ProviderResult.workflow_run_id == self.run_id, ProviderResult.operation == operation, ProviderResult.input_hash == digest))
            return row.payload if row else None

    async def save(self, operation, digest, payload):
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 512 * 1024:
            return
        async with AsyncSessionLocal() as db:
            await self._claim(db)
            await db.execute(insert(ProviderResult).values(id=uuid.uuid4(),research_task_id=self.task_id,
                workflow_run_id=self.run_id,operation=operation,input_hash=digest,payload=payload,
                created_at=datetime.now(timezone.utc)).on_conflict_do_nothing(constraint='uq_provider_result_unit'))
            await db.commit()

    async def writing_progress(self, completed, total):
        async with AsyncSessionLocal() as db:
            task = await self._claim(db)
            task.budget_config = {**task.budget_config, '_writer_progress': {
                'completed': completed, 'total': total, 'run_id': str(self.run_id)}}
            await db.commit()
