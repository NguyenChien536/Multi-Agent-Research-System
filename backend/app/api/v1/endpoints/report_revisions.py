import uuid
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.report_revision import ReportRevision
from app.schemas.report_revision import ReportRevisionCreate, ReportRevisionResponse
from app.services.report_questions import owned_version
from app.services.report_revisions import create_revision, reconcile_revisions

router = APIRouter()


@router.post("/{task_id}/report/versions/{version_number}/revisions", response_model=ReportRevisionResponse, status_code=202)
async def revise(task_id: uuid.UUID,version_number: int,payload: ReportRevisionCreate,response: Response,
                 db: AsyncSession=Depends(get_db),user: User=Depends(get_current_user)):
    request = await create_revision(db,task_id,version_number,user.id,payload)
    response.headers["Cache-Control"] = "private, no-store"
    return request


@router.get("/{task_id}/report/versions/{version_number}/revisions",response_model=list[ReportRevisionResponse])
async def history(task_id: uuid.UUID,version_number: int,response: Response,
                  offset: int=Query(0,ge=0),limit: int=Query(20,ge=1,le=100),
                  db: AsyncSession=Depends(get_db),user: User=Depends(get_current_user)):
    task,base = await owned_version(db,task_id,version_number,user.id,lock=True)
    await reconcile_revisions(db,task)
    rows = (await db.scalars(select(ReportRevision).where(ReportRevision.base_version_id == base.id,ReportRevision.research_task_id == task.id,
        ReportRevision.user_id == user.id).order_by(ReportRevision.created_at.desc(),ReportRevision.id.desc())
        .offset(offset).limit(limit))).all()
    await db.commit()
    response.headers["Cache-Control"] = "private, no-store"
    return rows
