<div align="center">

# 🌐 Synthia — Multi-Agent Research System

### *Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập*

[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF4F00.svg?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL: 16 + pgvector](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Broker-Redis%207-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![Docker: Ready](https://img.shields.io/badge/Docker-Compose%20Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/NguyenChien536/Multi-Agent-Research-System/pulls)

<p align="center">
  <a href="#-tổng-quan-kiến-trúc">Kiến trúc</a> •
  <a href="#-năng-lực-và-trạng-thái">Năng lực và trạng thái</a> •
  <a href="#-khởi-chạy-nhanh">Khởi chạy nhanh</a> •
  <a href="#-cấu-hình-môi-trường">Cấu hình</a> •
  <a href="#-hướng-dẫn-sử-dụng--api">API & Sử dụng</a> •
  <a href="#-kế-hoạch-đánh-giá-chưa-có-benchmark-được-xác-minh">Kế hoạch đánh giá</a> •
  <a href="#-đóng-góp">Đóng góp</a>
</p>

</div>
---

## 📖 Mục lục

- [💡 Đặt vấn đề & Giải pháp](#-đặt-vấn-đề--giải-pháp)
- [✨ Năng lực và trạng thái](#-năng-lực-và-trạng-thái)
- [📚 Tài liệu Dự án](#-tài-liệu-dự-án)
- [🏗️ Tổng quan Kiến trúc](#️-tổng-quan-kiến-trúc)
- [📁 Cấu trúc Thư mục Dự án](#-cấu-trúc-thư-mục-dự-án)
- [🚀 Khởi chạy Nhanh (Quick Start)](#-khởi-chạy-nhanh-quick-start)
  - [Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng)](#cách-1-khởi-chạy-bằng-docker-compose-khuyên-dùng)
  - [Cách 2: Cài đặt cho Môi trường Phát triển (Local Dev)](#cách-2-cài-đặt-cho-môi-trường-phát-triển-local-dev)
- [⚙️ Cấu hình Biến Môi trường (.env)](#️-cấu-hình-biến-môi-trường-env)
- [📡 Hướng dẫn Sử dụng & API Endpoints](#-hướng-dẫn-sử-dụng--api-endpoints)
- [📊 Kế hoạch đánh giá](#-kế-hoạch-đánh-giá-chưa-có-benchmark-được-xác-minh)
- [🗺️ Lộ trình Phát triển (Roadmap)](#️-lộ-trình-phát-triển-roadmap)
- [🤝 Hướng dẫn Đóng góp (Contributing)](#-hướng-dẫn-đóng-góp-contributing)
- [📄 Giấy phép (License)](#-giấy-phép-license)

---

## 💡 Đặt vấn đề & Giải pháp

Người nghiên cứu cần tìm và đối chiếu nhiều nguồn, thiết kế phương pháp, kiểm tra kết quả và viết bài có căn cứ. Một câu trả lời trôi chảy hoặc citation tồn tại chưa chứng minh kết luận đúng. Giá trị của việc dùng nhiều agent cần được so sánh thực nghiệm với single-agent có tools và cùng nguồn.

**ATI — Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập** hướng tới một **bản thảo bài báo hoàn chỉnh cho mỗi task** qua ba đường: tổng quan từ web/PDF (REVIEW), thí nghiệm tính toán trong phạm vi được hỗ trợ (EMPIRICAL_COMPUTATIONAL), và nghiên cứu con người thực hiện bên ngoài rồi nạp kết quả thực (EMPIRICAL_HUMAN). Protocol của đường human-led là artifact trung gian. Một user có thể làm bài B khi bài A đang chờ dữ liệu; mỗi bài có state và file riêng. Có hỏi đáp/sửa bài, report versions và tiến độ agent.

Bản chốt cập nhật 09/10/2026 yêu cầu một experiment CSV chạy thật trước 10/11, cùng citation/provenance, durable waits và đánh giá baseline/ablation. Tổng quan/human-led protocol nhận nhiều lĩnh vực; execution tự động ban đầu giới hạn routine numeric CSV. Thiếu dữ liệu/kết quả thật thì bài empirical tiếp tục chờ hoặc cần review, không tự sinh Results hay cam kết bài đủ điều kiện công bố. [User Journey và Outputs](docs/project/user-journey-and-outputs.md) mô tả luồng sử dụng đầy đủ.

| Vai trò agent mục tiêu | Trách nhiệm |
|---|---|
| Supervisor | Lập plan/version, scope và route trong policy/budget |
| Researcher | Search/query và thu thập thêm theo thiếu sót |
| Evidence Analyst | Claim/evidence, tổng hợp, mâu thuẫn và gợi ý khoảng trống nghiên cứu |
| Methodologist | Giả thuyết/phương pháp/protocol khi phù hợp |
| Data Analyst | Chọn routine cho phép và diễn giải actual outputs |
| Writer | Bản thảo đúng loại và có provenance |
| Critic | Kiểm cả bài cùng evidence/method/results; phản hồi có cấu trúc |

Curator/ingestion, router, citation validator, budget và runner là mô-đun code/tools. REVIEW không bắt buộc gọi đủ bảy vai trò. Kiến trúc là modular monolith với API/worker, không phải mỗi agent một microservice. Đây là **thiết kế mục tiêu**, trạng thái triển khai ghi riêng bên dưới.

---

## ✨ Năng lực và trạng thái

**Cập nhật 22/10/2026:** source baseline `develop@3bbeb01`. Dự án đang phát triển; đã có nhiều chức năng P1–P5 nhưng chưa khép toàn bộ acceptance gates và chưa sẵn sàng production.

| Năng lực | Bằng chứng gần nhất | Phần còn thiếu |
|---|---|---|
| Auth/ownership, outbox, quota RUNNING, worker recovery | Backend suite **74 passed**; PR #38 đã merge; GitHub CI **5/5 đạt** | Sửa client auth/me; cancellation/late writes và fault test runtime còn cần hoàn thiện |
| Research/evidence/citation workflow | Có code và provider-mocked integration; biên bản 18/10 có report lịch sử còn lưu | Budget trước call, Critic toàn bài, provider smoke trên candidate hiện tại |
| PDF, approval, human-led và computational routine | Đã triển khai các đường cơ bản và có tests | Intake UUID/provenance, checkpoint bền vững, runner riêng, journal trước execution |
| Next.js frontend | Frontend local hiện tại **lint/build đạt**, đã nối nhiều API | Chưa kiểm browser E2E trong audit này; không coi build là nghiệm thu UX |
| Runtime và deployment | DB migration `d1e2f3a4b5c6`; API **200**, Redis **PONG**, Celery **pong** | Compose dev; chưa có staging/restore/pilot để phát hành production |

[Kế hoạch triển khai](docs/project/implementation-plan.md) đã chốt thứ tự sửa và các chặng đến production. [Roadmap](docs/project/roadmap-and-progress.md) và [biên bản 22/10](docs/project/baseline-verification.md#kiem-tra-2026-10-22) ghi bằng chứng cùng giới hạn. **10/11 là mốc nộp/demo, chưa phải cam kết production.**

Không gọi hệ thống là “zero hallucination”. Citation trỏ tới source/chunk là kiểm tra tham chiếu; mức độ nguồn hỗ trợ claim cần đánh giá ngữ nghĩa riêng.

## 📚 Tài liệu Dự án

- Để biết **đọc gì, dự án đang ở đâu và làm gì tiếp theo**, bắt đầu tại [Hướng dẫn tài liệu dự án](docs/README.md).
- [Báo cáo giữa kỳ](docs/project/midterm-report.md).

---

## 🏗️ Tổng quan Kiến trúc

Để tránh sơ đồ trong README lệch với thiết kế hiện hành, các diagram được quản lý tập trung. Chúng mô tả **target design**, không khẳng định prototype đã triển khai đầy đủ.

- [C4 Container, Logical DFD, inference flow, async sequence và target ERD](docs/architecture/system-design.md)
- [HLD: boundary, trách nhiệm container và trade-offs](docs/architecture/system-architecture.md)
- [Agent roles, state và research loops](docs/technical/agent-workflow.md)

---

## 📁 Cấu trúc Thư mục Dự án

```text
MultiAgent Research System/
├── backend/
│   ├── app/
│   │   ├── agents/          # Định nghĩa LangGraph State, Nodes và Multi-Agent Graph
│   │   ├── api/v1/          # FastAPI REST endpoints (Task CRUD cơ bản, Health)
│   │   ├── core/            # App Configuration, Database async engine, Security
│   │   ├── db/              # Session maker và Database base models
│   │   ├── models/          # 12 Entities SQLAlchemy (Task, Source, Claim, Evidence, Chunk...)
│   │   ├── schemas/         # Pydantic v2 schemas phục vụ Request/Response validation
│   │   ├── tools/           # Tavily, async scraper, embedder và vector retrieval prototype
│   │   ├── worker.py        # Celery Application & Task Workers
│   │   └── main.py          # FastAPI application factory & Middlewares
│   ├── Dockerfile           # Docker image đa giai đoạn cho Backend & Celery Worker
│   └── requirements.txt     # Danh sách thư viện Python & Agent dependencies
├── frontend/                # Next.js starter UI; cần hoàn thiện trải nghiệm và tích hợp API/SSE
├── docker/
│   └── init-db.sql          # SQL Script kích hoạt PostgreSQL extensions (pgvector & uuid-ossp)
├── .env.example             # Bản mẫu biến môi trường chuẩn
├── docker-compose.yml       # Điều phối PostgreSQL, Redis, FastAPI Backend, Celery Worker
├── pyproject.toml           # Cấu hình dự án Python & Linter
└── README.md                # Tài liệu hướng dẫn sử dụng & Kiến trúc hệ thống
```

---

## 🚀 Khởi chạy (chưa xác minh trên mọi môi trường)

> **Trạng thái kiểm tra 22/10/2026:** local runtime và 74 backend tests đạt; frontend lint/build đạt. Các giới hạn và lỗi đã tái hiện được ghi ở [Roadmap](docs/project/roadmap-and-progress.md). Chưa có đủ evidence trên release candidate để coi là bản production; dùng [Implementation Plan](docs/project/implementation-plan.md) cho thứ tự triển khai.

### Yêu cầu Tiên quyết
* [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) (khuyên dùng v2.20+)
* [Git](https://git-scm.com/)
* Khóa API: **Tavily API Key** ([Đăng ký miễn phí tại đây](https://tavily.com/)) và **OpenAI API Key** hoặc **Anthropic API Key**.

---

### Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng)

Chỉ với 3 bước để khởi động toàn bộ hạ tầng (PostgreSQL, pgvector, Redis, FastAPI, Celery Worker):

#### 1. Clone mã nguồn
```bash
git clone https://github.com/NguyenChien536/Multi-Agent-Research-System.git
cd "Multi-Agent-Research-System"
```

#### 2. Cấu hình biến môi trường
Tạo file `.env` từ file mẫu:
```bash
cp .env.example .env
```
Mở file `.env` và điền các API Key của bạn:
```env
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
# Hoặc sử dụng Anthropic:
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
```

#### 3. Khởi chạy toàn bộ hệ thống
```bash
docker compose up -d --build
```

Kiểm tra trạng thái các dịch vụ đang chạy:
```bash
docker compose ps
```

Khi khởi chạy thành công, bạn có thể truy cập ngay:
* 📘 **FastAPI Swagger Docs (Kiểm thử API):** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
* 🩺 **Health Check Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
* 🗄️ **PostgreSQL + pgvector:** Cổng host `5433` (container `5432`)
* ⚡ **Redis Broker:** Cổng `6379`

Dừng hệ thống khi không sử dụng:
```bash
docker compose down
```

---

### Cách 2: Cài đặt cho Môi trường Phát triển (Local Dev)

Nếu bạn muốn chỉnh sửa mã nguồn và debug trực tiếp trên máy:

#### 1. Khởi chạy Database & Redis bằng Docker
```bash
docker compose up -d postgres redis
```

#### 2. Thiết lập Môi trường Ảo Python
```bash
cd backend
python -m venv .venv

# Trên Windows:
.venv\Scripts\activate
# Trên Linux/macOS:
source .venv/bin/activate

# Cài đặt thư viện:
pip install -r requirements.txt
```

#### 3. Chạy API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. Khởi chạy Celery Worker (ở terminal riêng biệt)
```bash
# Trên Windows:
celery -A app.worker.celery_app worker --loglevel=info -P solo
# Trên Linux/macOS:
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4
```

---

## ⚙️ Cấu hình Biến Môi trường (.env)

| Biến Môi trường | Kiểu dữ liệu | Giá trị Mặc định | Ý nghĩa & Mô tả |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | `string` | `development` | Môi trường triển khai (`development` / `production`). |
| `API_V1_STR` | `string` | `/api/v1` | Tiền tố đường dẫn API. |
| `DATABASE_URL` | `string` | *URL Postgres Async* | Kết nối CSDL Async (`postgresql+asyncpg://...`). |
| `REDIS_URL` | `string` | `redis://redis:6379/0` | Kết nối Redis cho Celery broker & Pub/Sub. |
| `TAVILY_API_KEY` | `string` | **Bắt buộc** | Khóa API Tavily phục vụ tìm kiếm & cào dữ liệu web. |
| `OPENAI_API_KEY` | `string` | Tùy chọn | Khóa API OpenAI (dùng cho GPT-4o và Embeddings). |
| `ANTHROPIC_API_KEY` | `string` | Tùy chọn | Khóa API Anthropic (dùng cho Claude 3.5 Sonnet). |
| `EMBEDDING_MODEL` | `string` | `text-embedding-3-small` | Tên mô hình vector hóa tri thức. |
| `DEFAULT_BUDGET_USD` | `float` | `2.00` | Giá trị cấu hình; guard xuyên provider/run là mục tiêu SRS v4.1, chưa được xác minh thực thi. |
| `DEFAULT_MAX_LLM_CALLS` | `integer` | `50` trong source hiện tại | Target SRS v4.1 là 40 calls; thay sau khi budget gateway được implement và kiểm chứng. |
| `LANGSMITH_TRACING` | `boolean` | `false` | Bật/tắt giám sát vết thực thi trên LangSmith. |

---

## 📡 Hướng dẫn Sử dụng & API Endpoints

### 1. Tạo mới một Đề tài Nghiên cứu (Create Task)

Gửi yêu cầu khởi tạo nghiên cứu thông qua HTTP POST:

```bash
curl -X POST "http://localhost:8000/api/v1/research" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Nghiên cứu Thị trường Xe điện Việt Nam 2026",
    "research_question": "Phân tích xu hướng chuyển dịch xe điện tại Việt Nam, cơ sở hạ tầng trạm sạc và thị phần VinFast so với các hãng xe Trung Quốc năm 2026.",
    "research_depth": "deep",
    "language": "vi",
    "max_sources": 15,
    "max_iterations": 2,
    "citation_style": "IEEE",
    "budget": {
      "max_cost_usd": 1.5,
      "max_llm_calls": 30,
      "timeout_seconds": 300
    }
  }'
```

**Mã phản hồi mẫu (`201 Created`):**
```json
{
  "id": "67b8a1c9-3e2b-4fa8-9e6b-7cb85a123456",
  "title": "Nghiên cứu Thị trường Xe điện Việt Nam 2026",
  "status": "PENDING",
  "created_at": "2026-09-20T10:15:30Z"
}
```

---

### 2. Kích hoạt Workflow Đa tác tử (Start Execution)

Sau khi tạo task, gọi endpoint `/start` để đưa tác vụ vào hàng đợi Celery:

```bash
curl -X POST "http://localhost:8000/api/v1/research/67b8a1c9-3e2b-4fa8-9e6b-7cb85a123456/start"
```

Endpoint ghi yêu cầu chạy qua outbox để Celery worker gọi LangGraph. Tests ngày 22/10 dùng provider giả; biên bản 18/10 có ghi một run thật, nhưng chưa chạy lại provider/browser E2E trên candidate hiện tại. Kiểm budget, resume/cancel, report/citations và UI theo các gate trong kế hoạch trước khi phát hành.

---

### 3. Kiểm tra Trạng thái & Lấy Báo cáo Cuối cùng

```bash
curl -X GET "http://localhost:8000/api/v1/research/67b8a1c9-3e2b-4fa8-9e6b-7cb85a123456"
```

Ví dụ dưới đây chỉ minh họa định dạng báo cáo dự kiến, không phải kết quả đã được hệ thống tạo hoặc citation đã xác minh:
```markdown
# Báo cáo Nghiên cứu: Chuyển Dịch Thị Trường Xe Điện Việt Nam 2026

## 1. Tổng quan Xu hướng
[Nhận định phải dựa trên evidence đã xác minh; số liệu lấy nguyên từ nguồn được trích dẫn] [1]...

## 2. Phân tích Hạ tầng Trạm Sạc
...

---
## Danh mục Tài liệu Tham khảo
[1] [Tác giả/tổ chức, tiêu đề, ngày, URL/DOI của nguồn thực tế]
[2] [Nguồn thứ hai đã đọc và xác minh]
```

---

## 📊 Kế hoạch đánh giá (chưa có benchmark được xác minh)

| Chỉ số cần đo | Cách đánh giá |
|---|---|
| Citation integrity | Tỷ lệ citation trỏ tới source/chunk tồn tại và thuộc đúng task. |
| Claim support | Người đánh giá gán nhãn claim/evidence; báo cáo precision/recall hoặc tỷ lệ hỗ trợ trên test set versioned. |
| Coverage/diversity | Mức bao phủ câu hỏi con, loại nguồn, thời gian và quan điểm đối lập. |
| Hiệu năng/chi phí | Median/range latency, lỗi, token/cost trên mẫu nhỏ; không trình bày như SLA. |

Chỉ so sánh với prompting/RAG cơ bản sau khi chạy cùng bộ câu hỏi, nguồn đầu vào, model/budget và rubric đánh giá; không dùng bảng tính năng chủ quan như benchmark.

---

## 🗺️ Lộ trình Phát triển (Roadmap)

Lộ trình chi tiết, thời hạn, phụ trách và trạng thái theo evidence nằm tại [roadmap-and-progress.md](docs/project/roadmap-and-progress.md). Định hướng mở rộng người dùng theo release gates: cá nhân/nhà nghiên cứu trước; chuyên gia và nhiều loại phương pháp sau khi chất lượng được đánh giá; nhóm/tổ chức chỉ sau khi có collaboration, tenant isolation, privacy và operational controls. Đây là định hướng, không phải cam kết phát hành.

Mốc 10/11/2026 gồm review web+PDF, một experiment CSV thật, protocol trung gian/wait/resume, bài empirical sau khi có kết quả thật, Q&A/revision và evaluation. Runner phải qua gate trước khi chạy; chưa đạt thì ghi feature còn thiếu, không thay bằng mock. Ảnh, PDF đẹp, arbitrary-code execution và cộng tác để sau. Thứ tự P0–P7 ở Implementation Plan.

---

## 🤝 Hướng dẫn Đóng góp (Contributing)

Chiến triển khai chính trên các nhánh `feature/<issue>-<slug>`, `bugfix/<issue>-<slug>`, `chore/<slug>` hoặc `docs/<slug>` tạo từ `develop`. Mỗi lát cắt đi qua Pull Request vào `develop`; chỉ đưa `develop` lên `main` sau khi toàn bộ check/test bắt buộc đạt và có bằng chứng nghiệm thu phù hợp. [CONTRIBUTING.md](CONTRIBUTING.md) ghi lệnh Git, mẫu PR và CI/CD. Người đóng góp khác có thể fork và gửi PR vào `develop` theo cùng quy tắc.

---

## 📄 Giấy phép (License)

Repository hiện chưa có file `LICENSE`; README không tuyên bố dự án dùng MIT. Hãy thêm giấy phép sau khi chủ dự án chốt điều khoản phát hành.

---

<div align="center">

⭐ **Nếu bạn thấy dự án này hữu ích, hãy tặng chúng tôi một Star trên GitHub!** ⭐

*Được phát triển với niềm đam mê dành cho Cộng đồng Trí tuệ Nhân tạo & Tự động hóa Nghiên cứu.*

</div>
