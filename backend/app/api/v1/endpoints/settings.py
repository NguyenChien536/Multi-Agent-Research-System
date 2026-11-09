"""Owner-scoped model preferences. Keys are write-only and encrypted at rest."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.task import ResearchTask

from app.schemas.model_settings import ConnectionUpdate, ModelCatalogRequest, ConnectionCheck
from app.services.user_model_settings import settings_id, decode_input, public_profile, updated_input, protect

router = APIRouter()


@router.post('/model-connection/check')
async def check_saved_or_draft_connection(payload: ConnectionCheck, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.model_connection_check import check_connection
    stored,binding = user.model_connection,settings_id(user.id)
    if payload.task_id:
        task = await db.scalar(select(ResearchTask).where(ResearchTask.id==payload.task_id,
            ResearchTask.user_id==user.id,ResearchTask.status!='DELETING'))
        if task is None:
            raise HTTPException(404,'Research task not found')
        stored,binding = (task.budget_config or {}).get('_llm_connection'),task.id
    update = ConnectionUpdate.model_validate(payload.model_dump(exclude={'task_id','generate','free_tier_confirmed'}))
    value = updated_input(update,stored,user.id,binding)
    return await check_connection(value,generate=payload.generate,free_tier_confirmed=payload.free_tier_confirmed)


@router.post('/model-connection/models')
async def list_connection_models(payload: ModelCatalogRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.model_catalog import discover_models
    from app.services.model_connection import validate_api_root
    try:
        root = validate_api_root(payload.base_url)
    except ValueError:
        raise HTTPException(422, 'Choose a trusted API service') from None
    stored, binding = user.model_connection, settings_id(user.id)
    if payload.task_id:
        task = await db.scalar(select(ResearchTask).where(ResearchTask.id == payload.task_id,
            ResearchTask.user_id == user.id, ResearchTask.status != 'DELETING'))
        if task is None:
            raise HTTPException(404, 'Research task not found')
        stored, binding = (task.budget_config or {}).get('_llm_connection'), task.id
    if payload.api_key is not None:
        key = payload.api_key.get_secret_value()
        if key != key.strip() or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise HTTPException(422, 'API key must not contain spaces or control characters')
    else:
        try:
            previous = decode_input(stored, user.id, binding)
        except ValueError:
            raise HTTPException(409, 'Enter a new API key to restore this connection') from None
        if previous is None or previous.base_url != root:
            raise HTTPException(400, 'Enter an API key for the selected service first')
        key = previous.api_key.get_secret_value()
    return await discover_models(root, key, payload.free_only)

@router.get('/model-connection')
async def get_connection(user: User = Depends(get_current_user)):
    return public_profile(user.model_connection)

@router.put('/model-connection')
async def save_connection(payload: ConnectionUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    owner = await db.scalar(select(User).where(User.id == user.id).with_for_update())
    value = updated_input(payload, owner.model_connection, user.id, settings_id(user.id))
    owner.model_connection = protect(value, settings_id(user.id), user.id)
    await db.commit()
    return public_profile(owner.model_connection)

@router.delete('/model-connection', status_code=204)
async def remove_connection(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    owner = await db.scalar(select(User).where(User.id == user.id).with_for_update())
    owner.model_connection = None
    await db.commit()
    # Existing task snapshots remain explicitly managed by each task.
    return Response(status_code=204)

@router.put('/research/{task_id}/model-connection')
async def update_task_connection(task_id: uuid.UUID, payload: ConnectionUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.scalar(select(ResearchTask).where(ResearchTask.id == task_id,
        ResearchTask.user_id == user.id, ResearchTask.status != 'DELETING').with_for_update())
    if task is None:
        raise HTTPException(404, 'Research task not found')
    if task.status in {'RUNNING', 'QUEUED'}:
        raise HTTPException(409, 'Stop the research before changing its API connection')
    stored = (task.budget_config or {}).get('_llm_connection')
    value = updated_input(payload, stored, user.id, task.id)
    task.budget_config = {**(task.budget_config or {}), '_llm_connection': protect(value, task.id, user.id)}
    await db.commit()
    return public_profile(task.budget_config['_llm_connection'])

@router.post('/research/{task_id}/use-default')
async def apply_default(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    owned = await db.scalar(select(ResearchTask.id).where(ResearchTask.id == task_id,
        ResearchTask.user_id == user.id, ResearchTask.status != 'DELETING'))
    if owned is None:
        raise HTTPException(404, 'Research task not found')
    try:
        value = decode_input(user.model_connection, user.id, settings_id(user.id))
    except ValueError:
        raise HTTPException(409, 'Update your API connection in Settings first') from None
    if value is None:
        raise HTTPException(409, 'Save an API connection in Settings first')
    return await update_task_connection(task_id, ConnectionUpdate(**value.model_dump()), db, user)

@router.post('/research/{task_id}/save-as-default')
async def save_task_as_default(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    owner = await db.scalar(select(User).where(User.id == user.id).with_for_update())
    task = await db.scalar(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == user.id, ResearchTask.status != 'DELETING'))
    if task is None:
        raise HTTPException(404, 'Research task not found')
    try:
        value = decode_input((task.budget_config or {}).get('_llm_connection'), user.id, task.id)
    except ValueError:
        raise HTTPException(409, 'Restore the article connection before saving it as default') from None
    if value is None:
        raise HTTPException(409, 'This article has no private API connection')
    owner.model_connection = protect(value, settings_id(user.id), user.id)
    await db.commit()
    return public_profile(owner.model_connection)
