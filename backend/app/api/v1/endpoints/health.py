import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from app.core.config import settings
from app.core.database import AsyncSessionLocal

router = APIRouter()


async def _database_ready() -> bool:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return True


async def _broker_ready() -> bool:
    client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()


@router.get("/ready")
async def readiness_check():
    """Dependency readiness, distinct from process liveness. Never expose connection details."""
    async def check(operation):
        try:
            return bool(await asyncio.wait_for(operation(), timeout=3))
        except Exception:
            return False

    database, broker = await asyncio.gather(check(_database_ready), check(_broker_ready))
    ready = database and broker
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "unavailable", "database": database, "broker": broker},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/health")
async def health_check():
    """Endpoint kiểm tra tình trạng hoạt động của API Service."""
    return {
        "status": "healthy",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
