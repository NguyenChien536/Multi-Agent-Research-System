"""Model connection discovery and task-level revocation."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.task import ResearchTask
from app.models.user import User

router = APIRouter()

@router.get("/model-connections/options")
async def model_connection_options():
    """Public connection catalog only; credentials and research remain private."""
    provider_keys = {'gemini': settings.GEMINI_API_KEY, 'openai': settings.OPENAI_API_KEY,
                     'anthropic': settings.ANTHROPIC_API_KEY, 'groq': settings.GROQ_API_KEY}
    provider = next((name.strip().lower() for name in settings.LLM_PROVIDER_PRIORITY.split(',')
                     if provider_keys.get(name.strip().lower()) and 'your_' not in provider_keys[name.strip().lower()]), None)
    return {"protocol": "openai_compatible", "base_urls": [root.strip().rstrip('/')
        for root in settings.CUSTOM_LLM_API_ROOTS.split(',') if root.strip()],
        'use_server_providers': settings.USE_SERVER_PROVIDERS,
        'server_provider_ready': provider is not None, 'server_provider': provider}

@router.get('/model-connections/free-models')
async def free_model_options():
    from app.services.model_catalog import free_models
    try:
        return {'models': await free_models()}
    except Exception:
        raise HTTPException(503, 'Model catalog is unavailable; enter the exact model ID manually') from None


@router.delete("/{task_id}/model-connection", status_code=204)
async def revoke_model_connection(task_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                  current_user: User = Depends(get_current_user)):
    task = await db.scalar(select(ResearchTask).where(ResearchTask.id == task_id,
        ResearchTask.user_id == current_user.id, ResearchTask.status != "DELETING").with_for_update())
    if task is None:
        raise HTTPException(404, "Research task not found")
    config = dict(task.budget_config or {})
    if stored := config.get('_llm_connection'):
        config['_llm_connection'] = {'profile': stored.get('profile', {}), 'revoked': True}
        task.budget_config = config
        await db.commit()
    return Response(status_code=204)
