import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router
from app.services.task_dispatcher import outbox_dispatch_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    dispatcher = asyncio.create_task(outbox_dispatch_loop(), name="task-outbox-dispatcher")
    try:
        yield
    finally:
        dispatcher.cancel()
        try:
            await dispatcher
        except asyncio.CancelledError:
            pass


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )

    # Cấu hình CORS
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Đăng ký API Routers
    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application


app = create_application()
