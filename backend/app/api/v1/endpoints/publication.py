import base64
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.task import ResearchTask
from app.models.report import ResearchReport, ReportVersion
from app.models.grounding import Citation
from app.models.source import ResearchSource
from app.services.publication_export import build_publication_bundle

router = APIRouter()


@router.get("/{task_id}/report/versions/{version_number}/publication")
async def export_publication(
    task_id: uuid.UUID,
    version_number: int,
    response: Response,
    template: Literal["IEEE_CONFERENCE", "ACM_SIGCONF"] = "IEEE_CONFERENCE",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a version-pinned, private source archive; never run arbitrary TeX."""
    version = await db.scalar(select(ReportVersion).join(ResearchReport).join(
        ResearchTask, ResearchTask.id == ResearchReport.research_task_id
    ).where(ResearchTask.id == task_id, ResearchTask.user_id == user.id,
            ResearchTask.status != "DELETING", ReportVersion.version_number == version_number))
    if version is None:
        raise HTTPException(404, "Report version not found")
    rows = (await db.execute(select(Citation, ResearchSource).join(ResearchSource, Citation.source_id == ResearchSource.id).where(
        Citation.report_version_id == version.id, Citation.research_task_id == task_id,
        ResearchSource.research_task_id == task_id,
    ).order_by(Citation.citation_number))).all()
    citations = [{"source_id": str(source.id), "citation_label": citation.citation_label,
                  "source_title": source.title, "source_url": source.url,
                  "source_author": source.author, "publication_date": source.publication_date} for citation, source in rows]
    snapshots = {(item.get("source_id"), item.get("citation_label")): item
                 for item in (version.review_metadata or {}).get("bibliography_snapshot", [])}
    # A snapshot can override mutable descriptive fields only after matching a
    # persisted citation in this version and this owner's task.
    citations = [snapshots.get((item["source_id"], item["citation_label"]), item) for item in citations]
    try:
        archive, manifest = build_publication_bundle(version.title, version.content_markdown,
            {**(version.review_metadata or {}), "status": version.review_status}, citations, template,
            version_id=str(version.id), version_number=version.version_number)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"Publication source cannot be generated: {type(exc).__name__}") from exc
    response.headers["Cache-Control"] = "private, no-store"
    return {"filename": f"paper-v{version_number}-{template.lower()}.zip", "archive_base64": base64.b64encode(archive).decode("ascii"),
            "report_version_id": str(version.id), "version_number": version_number, "template": template,
            "review_status": version.review_status, "official_template_source": manifest["official_template_source"]}
