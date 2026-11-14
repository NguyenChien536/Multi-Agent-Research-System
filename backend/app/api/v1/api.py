from fastapi import APIRouter
from app.api.v1.endpoints import settings as user_settings
from app.api.v1.endpoints import experiment_export
from app.api.v1.endpoints import (
    auth,
    health,
    monitoring,
    publication,
    report_questions,
    report_revisions,
    research,
    research_connections,
    research_files,
    research_read,
    research_study,
)

api_router = APIRouter()
api_router.include_router(user_settings.router, prefix='/settings', tags=['User Settings'])

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, tags=["System Health"])
api_router.include_router(research.router, prefix="/research", tags=["Research Tasks"])
api_router.include_router(research_read.router, prefix="/research", tags=["Research Reports and Sources"])
api_router.include_router(research_files.router, prefix="/research", tags=["Research Files"])
api_router.include_router(research_study.router, prefix="/research", tags=["Research Study and Experiments"])
api_router.include_router(research_connections.router, prefix="/research", tags=["Research Model Connections"])
api_router.include_router(monitoring.router, prefix="/research", tags=["Research Monitoring"])
api_router.include_router(report_questions.router, prefix="/research", tags=["Report Questions"])
api_router.include_router(publication.router, prefix="/research", tags=["Publication Sources"])
api_router.include_router(report_revisions.router, prefix="/research", tags=["Report Revisions"])
api_router.include_router(experiment_export.router, prefix="/research", tags=["Experiment Export"])
