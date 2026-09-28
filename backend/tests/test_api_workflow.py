import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app

# Sử dụng ASGITransport để test FastAPI trực tiếp không cần bật server
@pytest.mark.asyncio
async def test_research_workflow_e2e():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. POST /api/v1/research - Tạo task mới
        payload = {
            "title": "Test AI Research System",
            "research_question": "Làm thế nào để xây dựng Multi-Agent System với LangGraph?",
            "research_depth": "STANDARD",
            "language": "vi",
            "max_sources": 3,
            "max_iterations": 1,
            "report_length": "SHORT",
            "citation_style": "APA"
        }
        
        response = await ac.post("/api/v1/research", json=payload)
        assert response.status_code == 201
        
        task_data = response.json()
        assert "id" in task_data
        assert task_data["title"] == payload["title"]
        assert task_data["status"] == "PENDING"
        
        task_id = task_data["id"]
        
        # 2. GET /api/v1/research/{task_id} - Kiểm tra chi tiết
        response = await ac.get(f"/api/v1/research/{task_id}")
        assert response.status_code == 200
        assert response.json()["id"] == task_id
        
        # 3. POST /api/v1/research/{task_id}/start - Chạy workflow
        response = await ac.post(f"/api/v1/research/{task_id}/start")
        assert response.status_code == 200
        assert response.json()["status"] == "PLANNING"
        
        # Trong test này, chúng ta không chạy worker thật, chỉ test API endpoint.
        # Worker execution sẽ được test riêng hoặc trong E2E thật.
        
        # 4. GET /api/v1/research/{task_id}/report - Lấy báo cáo (sẽ lỗi 404 vì chưa chạy xong)
        response = await ac.get(f"/api/v1/research/{task_id}/report")
        assert response.status_code == 404
