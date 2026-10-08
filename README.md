<div align="center">

# 🌐 Multi-Agent Research System

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

**ATI — Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập** hỗ trợ ba đường: tổng quan từ web/PDF (REVIEW), phân tích/thí nghiệm tính toán trong phạm vi được hỗ trợ (EMPIRICAL), và protocol cho nghiên cứu con người thực hiện bên ngoài (PROTOCOL). Có hỏi đáp/sửa bài, report versions và tiến độ agent.

Bản chốt 08/10/2026 yêu cầu một experiment CSV chạy thật trước 10/11, cùng citation/provenance, durable waits và đánh giá baseline/ablation. Tổng quan/protocol nhận nhiều lĩnh vực; execution ban đầu giới hạn routine numeric CSV. Không tự sinh Results khi thiếu data hoặc cam kết bài đủ điều kiện công bố.

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

Repository hiện là **prototype/scaffold đang phát triển**. Bảng này phân biệt mã/thiết kế hiện có với tính năng cần hoàn thiện; “có mã nguồn” không đồng nghĩa đã chạy hoặc được kiểm thử.

| Năng lực | Trạng thái theo baseline 27/09/2026 | Ghi chú |
|---|---|---|
| FastAPI, schema/model và API quản lý task cơ bản | Có mã nguồn tại baseline | Route mẫu khi đó dùng `dummy_user_id`; code thay đổi sau baseline chưa được xác minh runtime. |
| LangGraph state và node | Có implementation prototype | Graph compile và routing mẫu đã smoke-test; workflow end-to-end và citation/evidence flow chưa xác minh. |
| Tavily search, scraping, embedding và pgvector retrieval | Có implementation trong source | Chưa xác minh provider thật hoặc ingestion/retrieval end-to-end. |
| Next.js frontend | Có starter UI | Chưa kiểm tra UX/API integration end-to-end; frontend dùng polling; SSE, HITL và PDF export chưa hoàn tất. |
| PostgreSQL/pgvector, Redis, Celery và Docker Compose | Đã chạy baseline trong môi trường phát triển 27/09/2026 | Health/OpenAPI, POST/GET task, worker ping và graph routing smoke-check đạt; không đồng nghĩa MVP/E2E đã nghiệm thu. |

Không gọi hệ thống là “zero hallucination”. Citation tag trỏ tới nguồn/chunk là kiểm tra tính toàn vẹn tham chiếu; mức độ nguồn hỗ trợ nội dung claim phải đánh giá riêng bằng test set và/hoặc người thẩm định.

## 📚 Tài liệu Dự án

- [Định hướng đã chốt](docs/project/product-assessment.md), [Kế hoạch triển khai](docs/project/implementation-plan.md), [Kế hoạch đánh giá](docs/project/evaluation-plan.md), [Technical Design: chức năng/công nghệ/patterns](docs/architecture/technical-design.md).
- [SRS hiện hành](docs/requirements/SRS.md) — yêu cầu, tiêu chí nghiệm thu, demo boundary và security gates.
- [Báo cáo giữa kỳ](docs/project/midterm-report.md) — overview, problems/objectives, technical approach, system design, plan, progress và AI disclosure.
- [System Design](docs/architecture/system-design.md) — nguồn chuẩn cho C4 Container, DFD, inference flow, async sequence, ERD, physical DFD và class diagram.
- [High-Level Architecture](docs/architecture/system-architecture.md) — container responsibilities, trade-offs, reliability và release boundary.
- [Roadmap và tiến độ](docs/project/roadmap-and-progress.md) — mốc thực hiện, phân công và progress theo evidence.
- [Baseline Verification](docs/project/baseline-verification.md) — lệnh và kết quả chạy gần nhất.
- [Toàn bộ docs](docs/README.md) — mục lục tài liệu theo đối tượng đọc.

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

> **Prototype notice:** Baseline Docker đã chạy ngày 27/09/2026: bốn service lên, PostgreSQL/Redis healthy, Alembic hiện ở `5ee074153cf3 (head)`, health/OpenAPI và POST/GET task đạt smoke-check, worker ping và graph routing mẫu đạt. Chưa kiểm tra migration trên DB sạch hoặc chạy research workflow end-to-end; SSE chưa được tích hợp vào API và frontend hiện polling. Đây là bằng chứng môi trường phát triển, không phải nghiệm thu production.

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
| `DEFAULT_BUDGET_USD` | `float` | `2.00` | Giá trị cấu hình; guard xuyên provider/run là mục tiêu SRS v4.0, chưa được xác minh thực thi. |
| `DEFAULT_MAX_LLM_CALLS` | `integer` | `50` trong source hiện tại | Target SRS v4.0 là 40 calls; thay sau khi budget gateway được implement và kiểm chứng. |
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

Endpoint đưa job vào Celery và worker có gọi LangGraph workflow trong source hiện tại. Tuy nhiên, baseline được ghi nhận chưa chạy workflow end-to-end với provider thật; chưa xác minh report/citation output, lỗi/retry và UI integration.

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

Mốc 10/11/2026 gồm review web+PDF, một experiment CSV thật, protocol/wait/resume, Q&A/revision và evaluation. Runner phải qua gate trước khi chạy; chưa đạt thì ghi feature còn thiếu, không thay bằng mock. Ảnh, PDF đẹp, arbitrary-code execution và cộng tác để sau. Thứ tự P0–P7 ở Implementation Plan.

---

## 🤝 Hướng dẫn Đóng góp (Contributing)

Chúng tôi luôn chào đón mọi đóng góp từ cộng đồng mã nguồn mở! Nếu bạn muốn đóng góp:

1. **Fork** repository này về tài khoản GitHub của bạn.
2. Tạo một nhánh tính năng mới (`git checkout -b feature/tinh-nang-moi`).
3. Commit những thay đổi của bạn (`git commit -m 'feat: thêm thuật toán lọc nguồn thông minh'`).
4. Push nhánh lên GitHub (`git push origin feature/tinh-nang-moi`).
5. Tạo một **Pull Request** mới để chúng tôi xem xét và gộp mã nguồn.

> Vui lòng tuân thủ quy tắc định dạng mã nguồn (PEP 8, Black, Ruff) trước khi gửi PR.

---

## 📄 Giấy phép (License)

Repository hiện chưa có file `LICENSE`; README không tuyên bố dự án dùng MIT. Hãy thêm giấy phép sau khi chủ dự án chốt điều khoản phát hành.

---

<div align="center">

⭐ **Nếu bạn thấy dự án này hữu ích, hãy tặng chúng tôi một Star trên GitHub!** ⭐

*Được phát triển với niềm đam mê dành cho Cộng đồng Trí tuệ Nhân tạo & Tự động hóa Nghiên cứu.*

</div>
