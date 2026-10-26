"""Read-only, owner-scoped snapshots assembled from durable research records."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.experiment import AnalysisRun
from app.models.grounding import ResearchClaim
from app.models.report import ExportArtifact, ReportVersion, ResearchReport
from app.models.source import ResearchSource
from app.models.task import ResearchTask, WorkflowRun
from app.schemas.monitoring import MonitorActivity, MonitorWorkflow, ResearchMonitorResponse


COUNTER_KEYS = {
    "queries_count", "sections_count", "sources_scraped", "visited_urls",
    "chunks_indexed", "verified_claims_count", "draft_words", "feedback_count",
    "missing_areas_count", "citations_count", "report_words",
}
VERDICTS = {"PASS", "REVISE", "NEED_MORE_DATA", "NEEDS_REVIEW", "IMPROVEMENT", "NO_IMPROVEMENT", "INCONCLUSIVE"}
AGENTS = {"Supervisor", "Researcher", "Curator", "Analyst", "Methodologist", "DataAnalyst", "ExperimentRunner", "Writer", "Critic", "PostProcessor"}


def safe_output(summary: dict) -> dict:
    """Only documented counters and finite verdict enums can reach the monitor."""
    if not isinstance(summary, dict):
        return {}
    result = {key: value for key, value in summary.items()
              if key in COUNTER_KEYS and type(value) is int and value >= 0}
    if isinstance(summary.get("verdict"), str) and summary["verdict"] in VERDICTS:
        result["verdict"] = summary["verdict"]
    if isinstance(summary.get("repeatability"), str) and summary["repeatability"] in {"PASSED", "FAILED", "NOT_RUN"}:
        result["repeatability"] = summary["repeatability"]
    if type(summary.get("budget_limited")) is bool:
        result["budget_limited"] = summary["budget_limited"]
    return result


def next_action(status: str, step: str | None, has_report: bool) -> str:
    if status == "WAITING_APPROVAL":
        return "REVIEW_PLAN"
    if status == "WAITING_USER_DATA":
        return "UPLOAD_DATA"
    if status == "PENDING":
        return "START_RESEARCH"
    if status == "FAILED":
        return "CHECK_FAILURE"
    if status == "CANCELLED":
        return "CANCELLED"
    if step == "BUDGET_LIMIT":
        return "REVIEW_LIMIT"
    if status in {"NEEDS_REVIEW", "PARTIAL"}:
        return "REVIEW_REPORT" if has_report else "REVIEW_RUN"
    if status == "COMPLETED":
        return "READ_REPORT" if has_report else "REPORT_UNAVAILABLE"
    return "WAIT"


async def research_snapshot(db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID,
                            offset: int, limit: int) -> ResearchMonitorResponse | None:
    def count(model, *conditions):
        return select(func.count(model.id)).where(model.research_task_id == task_id, *conditions).scalar_subquery()

    version_count = (select(func.count(ReportVersion.id)).join(ResearchReport)
                     .where(ResearchReport.research_task_id == task_id).scalar_subquery())
    # The task identity, lifecycle and output counts share one database statement.
    row = (await db.execute(select(
        ResearchTask,
        count(ResearchSource).label("sources"),
        count(ResearchSource, ResearchSource.ingestion_status.in_(["PENDING", "PROCESSING"])).label("pending_sources"),
        count(ResearchSource, ResearchSource.ingestion_status == "FAILED").label("failed_sources"),
        count(ResearchClaim, ResearchClaim.is_verified.is_(True)).label("verified_claims"),
        count(ExportArtifact).label("artifacts"),
        count(AnalysisRun).label("experiments"),
        count(AgentRun).label("activities"),
        version_count.label("report_versions"),
    ).where(ResearchTask.id == task_id, ResearchTask.user_id == user_id,
            ResearchTask.status != "DELETING"))).one_or_none()
    if row is None:
        return None
    task = row[0]
    now = datetime.now(timezone.utc)
    workflow = await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id == task_id)
                               .order_by(WorkflowRun.run_number.desc()).limit(1))
    activities = (await db.scalars(select(AgentRun).where(AgentRun.research_task_id == task_id)
                                  .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
                                  .offset(offset).limit(limit))).all()
    usage = (task.budget_config or {}).get("_provider_usage")
    if isinstance(usage, dict):
        cost = float(usage.get("cost_usd", 0))
        tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        reserved = sum(float(item.get("cost_usd", 0)) for item in usage.get("reservations", {}).values())
        accounting = "PROVIDER_LEDGER"
    else:
        totals = (await db.execute(select(func.coalesce(func.sum(AgentRun.estimated_cost), 0),
                                         func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0))
                                  .where(AgentRun.research_task_id == task_id))).one()
        cost, tokens, reserved, accounting = float(totals[0]), int(totals[1]), 0.0, "AGENT_HISTORY"
    return ResearchMonitorResponse(
        task_id=task.id, title=task.title, research_type=task.research_type, status=task.status,
        current_step=task.current_step, current_iteration=task.current_iteration,
        attempt_number=task.attempt_number, created_at=task.created_at, updated_at=task.updated_at,
        completed_at=task.completed_at, observed_at=now,
        worker_lease_expired=(task.worker_lease_until <= now if task.worker_lease_until else None)
                              if task.status == "RUNNING" else None,
        next_action=next_action(task.status, task.current_step, row.report_versions > 0),
        workflow=MonitorWorkflow(id=workflow.id, run_number=workflow.run_number, status=workflow.status,
                                 plan_version=workflow.plan_version, started_at=workflow.started_at,
                                 completed_at=workflow.completed_at) if workflow else None,
        counts={key: getattr(row, key) for key in ("sources", "pending_sources", "failed_sources",
                "verified_claims", "artifacts", "experiments", "report_versions")},
        estimated_cost_usd=cost, reserved_cost_usd=reserved, recorded_tokens=tokens,
        accounting_source=accounting, activity_total=row.activities, activity_offset=offset,
        activity_limit=limit,
        activities=[MonitorActivity(id=run.id, agent=run.agent_name if run.agent_name in AGENTS else "Other",
                    status=run.status if run.status in {"RUNNING", "SUCCESS", "FAILED"} else "UNKNOWN",
                    iteration=run.iteration, started_at=run.started_at, completed_at=run.completed_at,
                    duration_ms=run.duration_ms, output=safe_output(run.output_summary or {}),
                    has_error=bool(run.error_message)) for run in activities],
    )
