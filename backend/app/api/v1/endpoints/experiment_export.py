import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.report_questions import owned_version
from app.services.experiment_bundle import bundle_records, build_experiment_bundle

router = APIRouter()


@router.get("/{task_id}/report/versions/{version_number}/experiment-bundle/availability")
async def experiment_bundle_availability(task_id: uuid.UUID, version_number: int,
    response: Response, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task, version = await owned_version(db, task_id, version_number, user.id)
    response.headers["Cache-Control"] = "private, no-store"
    computational = ((version.review_metadata or {}).get("manuscript_input_snapshot") or {}).get("research_type") == "EMPIRICAL_COMPUTATIONAL"
    try:
        await bundle_records(db, task, version)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        return {"available": False, "computational": computational, "reason": exc.detail}
    return {"available": True, "computational": True, "report_version_id": str(version.id)}


@router.get("/{task_id}/report/versions/{version_number}/experiment-bundle")
async def export_experiment_bundle(task_id: uuid.UUID, version_number: int,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Lock only during bounded local reads/build, so a deletion cannot commit
    # between authorization and delivery. No external calls or routine execution.
    task, version = await owned_version(db, task_id, version_number, user.id, lock=True)
    content = await build_experiment_bundle(db, task, version)
    return Response(content, media_type="application/zip", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="experiment-v{version.version_number}.zip"'})
