import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.task import ResearchTask
from app.schemas.task import ResearchTaskCreate, ResearchTaskResponse
from app.worker import execute_research_workflow

router = APIRouter()


@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_research_task(
    task_in: ResearchTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """Tạo mới một Research Task."""
    # Tạm thời dùng mock user_id cho MVP Scaffolding
    dummy_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    budget_dict = task_in.budget.model_dump() if task_in.budget else {
        "max_cost_usd": 2.0,
        "max_llm_calls": 50,
        "max_input_tokens": 100000,
        "max_output_tokens": 50000,
        "timeout_seconds": 300,
    }
    
    task = ResearchTask(
        user_id=dummy_user_id,
        title=task_in.title,
        research_question=task_in.research_question,
        description=task_in.description,
        research_depth=task_in.research_depth,
        language=task_in.language,
        max_sources=task_in.max_sources,
        max_iterations=task_in.max_iterations,
        report_length=task_in.report_length,
        citation_style=task_in.citation_style,
        budget_config=budget_dict,
        status="PENDING",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("", response_model=List[ResearchTaskResponse])
async def list_research_tasks(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    """Lấy danh sách các Research Task."""
    result = await db.execute(select(ResearchTask).offset(skip).limit(limit).order_by(ResearchTask.created_at.desc()))
    return result.scalars().all()


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Xem thông tin chi tiết một Research Task."""
    result = await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return task


@router.post("/{task_id}/start", status_code=status.HTTP_200_OK)
async def start_research_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Bắt đầu chạy workflow nghiên cứu đa tác tử trong Celery background."""
    result = await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    
    task.status = "PLANNING"
    await db.commit()
    
    # Bắn task vào Celery Task Queue
    execute_research_workflow.delay(str(task_id))
    
    return {"status": "PLANNING", "message": "Workflow started successfully", "task_id": str(task_id)}
