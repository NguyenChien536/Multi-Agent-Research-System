import uuid
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

@router.get("/{task_id}/stream")
async def stream_task_progress(
    task_id: uuid.UUID,
    request: Request,
):
    """
    Streaming tiến trình nghiên cứu thời gian thực bằng Server-Sent Events (SSE).
    Trong kiến trúc hoàn chỉnh, dữ liệu sẽ được subscribe qua Redis Pub/Sub.
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        # TODO: Kết nối với Redis Pub/Sub để lắng nghe event theo task_id
        # Mẫu MVP: gửi heartbeat giả định
        try:
            for i in range(1, 101):
                if await request.is_disconnected():
                    break
                
                # Trả về format SSE chuẩn
                yield {
                    "event": "message",
                    "id": str(i),
                    "retry": 15000,
                    "data": f'{{"status": "RUNNING", "progress": {i}, "agent": "researcher"}}'
                }
                await asyncio.sleep(2)
                
            yield {
                "event": "complete",
                "data": '{"status": "COMPLETED"}'
            }
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
