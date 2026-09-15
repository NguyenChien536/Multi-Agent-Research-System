# Multi-Agent Research System

> Nền tảng Nghiên cứu Tự động Chuyên sâu sử dụng Kiến trúc Đa Tác tử (Multi-Agent System) phối hợp với Vector Database (RAG) và Quy trình Phản biện Độc lập (Critic Loop).

---

## 🏗️ Tổng quan Kiến trúc

Hệ thống được thiết kế theo kiến trúc phân tầng Enterprise (Clean Layered Architecture), gồm 5 Agent chính phối hợp nhịp nhàng:

1. **Supervisor Agent**: Phân tách đề tài, lập đề cương nghiên cứu và điều phối vòng lặp (Dual-loop).
2. **Researcher Agent**: Gọi Tavily Search API song song (`asyncio.gather`), cào dữ liệu và loại bỏ mã rác qua SSRF Guard.
3. **Curator & VectorDB**: Lọc trùng lặp URL bằng hash nội dung, băm chunks và vector hóa lưu vào PostgreSQL (`pgvector`).
4. **Analyst Agent**: Thực hiện Semantic Search trên VectorDB, khai phóng insight, trích xuất `Evidence` và xây dựng `ResearchClaim`.
5. **Writer & Critic Agents**: Vòng lặp phản biện khép kín (Micro-loop) giúp phát hiện và loại trừ 100% ảo giác (hallucination) trong văn phong báo cáo.
6. **Citation Validator & Post-Processor**: Đánh số trích dẫn bằng Python code deterministic và xuất bản báo cáo chuẩn học thuật (Markdown & PDF).

---

## 📁 Cấu trúc Thư mục Dự án

```
MultiAgent Research System/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST endpoints & SSE Streaming
│   │   ├── core/            # Config, Security, Database Async Engine
│   │   ├── models/          # 12 Entities SQLAlchemy (Tasks, Sources, Grounding, Evaluation...)
│   │   ├── schemas/         # Pydantic v2 validation schemas
│   │   ├── agents/          # LangGraph Workflow & Agent State definition
│   │   ├── worker.py        # Celery background tasks runner
│   │   └── main.py          # FastAPI application factory
│   ├── Dockerfile           # Docker container cho Backend & Worker
│   └── requirements.txt     # Danh sách thư viện Python
├── frontend/                # Next.js 14 App Router (Giao diện người dùng)
├── docker/
│   └── init-db.sql          # Khởi tạo PostgreSQL extensions (pgvector & uuid)
├── docker-compose.yml       # Điều phối PostgreSQL, Redis, Backend, Celery Worker
├── .env.example             # File mẫu biến môi trường
├── .gitignore               # Che giấu tài liệu nội bộ & secrets
└── README.md
```

---

## 🚀 Hướng dẫn Khởi chạy Nhanh

### 1. Yêu cầu Tiên quyết
* Cài đặt **Docker** & **Docker Compose**
* Khóa API: **Tavily API Key**, **Anthropic API Key** hoặc **OpenAI API Key**

### 2. Thiết lập Môi trường
Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Điền các API Key của bạn vào `.env`:
```env
TAVILY_API_KEY=your_tavily_key
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

### 3. Khởi chạy toàn bộ hệ thống bằng Docker
```bash
docker compose up -d --build
```

### 4. Kiểm tra dịch vụ
* **FastAPI Swagger Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
* **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
* **PostgreSQL + pgvector**: Port `5432`
* **Redis Broker**: Port `6379`
