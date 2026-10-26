import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.report_question import ReportQuestion
from app.models.user import User
from app.schemas.report_question import ReportQuestionCreate, ReportQuestionHistory, ReportQuestionResponse
from app.services.report_questions import ask_question, expire_questions, owned_version

router = APIRouter()


@router.post("/{task_id}/report/versions/{version_number}/questions", response_model=ReportQuestionResponse)
async def create_question(task_id: uuid.UUID, version_number: int, payload: ReportQuestionCreate,
                          response: Response, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    return await ask_question(db, task_id, version_number, current_user.id, payload)


@router.get("/{task_id}/report/versions/{version_number}/questions", response_model=ReportQuestionHistory)
async def question_history(task_id: uuid.UUID, version_number: int, response: Response,
                           offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                           db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _, version = await owned_version(db, task_id, version_number, current_user.id)
    await expire_questions(db, current_user.id)
    filters = (ReportQuestion.report_version_id == version.id, ReportQuestion.user_id == current_user.id)
    total = await db.scalar(select(func.count(ReportQuestion.id)).where(*filters))
    items = (await db.scalars(select(ReportQuestion).where(*filters)
        .order_by(ReportQuestion.created_at.desc(), ReportQuestion.id.desc()).offset(offset).limit(limit))).all()
    await db.commit()
    response.headers["Cache-Control"] = "private, no-store"
    return ReportQuestionHistory(report_version_id=version.id, version_number=version_number,
        items=[ReportQuestionResponse.model_validate(item) for item in items], total=total, offset=offset, limit=limit)
