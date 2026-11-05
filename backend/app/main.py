import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

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
    @application.exception_handler(RequestValidationError)
    async def redact_connection_validation(request, exc):
        # Pydantic normally echoes rejected input, including a nested secret.
        if isinstance(exc.body, dict) and {"llm_connection", "api_key", "password", "current_password"}.intersection(exc.body):
            return JSONResponse(status_code=422, content={"detail": [
                {"loc": list(error["loc"]), "type": error["type"],
                 "msg": "Invalid API connection configuration" if "llm_connection" in error["loc"] else "Invalid request value"}
                for error in exc.errors()
            ]})
        return await request_validation_exception_handler(request, exc)

    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application


app = create_application()
