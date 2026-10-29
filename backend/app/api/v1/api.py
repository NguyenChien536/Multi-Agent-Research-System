from fastapi import APIRouter
from app.api.v1.endpoints import health, research, auth, monitoring, report_questions, publication, report_revisions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, tags=["System Health"])
api_router.include_router(research.router, prefix="/research", tags=["Research Tasks"])
api_router.include_router(monitoring.router, prefix="/research", tags=["Research Monitoring"])
api_router.include_router(report_questions.router, prefix="/research", tags=["Report Questions"])
api_router.include_router(publication.router, prefix="/research", tags=["Publication Sources"])
api_router.include_router(report_revisions.router, prefix="/research", tags=["Report Revisions"])
