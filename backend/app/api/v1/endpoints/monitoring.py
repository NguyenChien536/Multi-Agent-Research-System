import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.monitoring import ResearchMonitorResponse
from app.services.monitoring import research_snapshot

router = APIRouter()


@router.get("/{task_id}/monitor", response_model=ResearchMonitorResponse)
async def monitor_research(
    task_id: uuid.UUID,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshot = await research_snapshot(db, task_id, current_user.id, offset, limit)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    response.headers["Cache-Control"] = "private, no-store"
    return snapshot
