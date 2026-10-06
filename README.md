<div align="center">

# 🌐 Multi-Agent Research System

### *Nền tảng Nghiên cứu Chuyên sâu Tự động hóa bằng Kiến trúc Đa Tác tử (Multi-Agent System)*

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

Trong kỷ nguyên bùng nổ thông tin, việc sử dụng các mô hình ngôn ngữ lớn (LLM) đơn lẻ (như ChatGPT, Claude) bằng một prompt trực tiếp thường bộc lộ những hạn chế cố hữu:

* ❌ **Ảo giác thông tin (Hallucination):** Tự bịa số liệu, sự kiện hoặc trích dẫn các liên kết không tồn tại.
* ❌ **Nông cạn & Thiếu cấu trúc:** Câu trả lời ngắn, không đào sâu vào các khía cạnh ngách của vấn đề.
* ❌ **Thiếu cơ chế tự sửa sai:** Khi gặp thông tin sai hoặc mâu thuẫn, LLM đơn lẻ không có quy trình phản biện để kiểm chứng chéo.

**Multi-Agent Research System** hướng tới hỗ trợ bước khảo sát ban đầu một chủ đề từ nguồn web công khai: lập kế hoạch, tổng hợp nguồn, trình bày claim/evidence và tạo bản báo cáo có thể kiểm tra. Hệ thống không loại bỏ hoàn toàn hallucination, không thay thế chuyên gia và không tự được xem là công cụ systematic review đạt chuẩn xuất bản.

ATI hướng tới hỗ trợ nhiều phương pháp nghiên cứu có giám sát, từ tìm và tổng hợp tài liệu đến protocol và phân tích dữ liệu có provenance. Demo/MVP trước 10/11/2026 ưu tiên một luồng literature review đầu-cuối; các phương pháp khác chỉ được tuyên bố hỗ trợ khi có implementation và evaluation evidence phù hợp.

Kiến trúc đích dự kiến gồm các vai trò phối hợp sau. Đây là mục tiêu thiết kế, không phải cam kết mọi thành phần đã hoạt động:

| Vai trò Agent | Chức năng tương ứng | Công nghệ áp dụng |
| :--- | :--- | :--- |
| 🧑‍💼 **Supervisor Agent** | Lập đề cương phân tầng, phân bổ tác vụ và điều phối | LangGraph State Graph & Dynamic Routing |
| 🕵️ **Researcher Agent** | Tìm kiếm mở rộng, cào dữ liệu web song song | Tavily Search API, Trafilatura, SSRF Guard |
| 🗄️ **Curator & VectorDB** | Khử trùng URL, chia đoạn ngữ nghĩa và vector hóa | pgvector (PostgreSQL 16), Cosine Similarity |
| 🧠 **Analyst Agent** | Khai phóng insight, tổng hợp luận điểm (`Claims`) kèm bằng chứng (`Evidence`) | Semantic RAG, Multi-query Retrieval |
| ⚖️ **Critic** | Lớp kiểm tra draft, nêu điểm thiếu bằng chứng/mâu thuẫn | Vai trò trong kiến trúc đích; cần evaluation để kiểm chứng chất lượng |
| ✍️ **Writer & Citation Validator** | Biên soạn báo cáo, đánh số trích dẫn chuẩn hóa | Regex Deterministic Citation `[1]`, `[2]` |

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
| `DEFAULT_BUDGET_USD` | `float` | `2.00` | Ngân sách chi phí trần cho mỗi phiên nghiên cứu. |
| `DEFAULT_MAX_LLM_CALLS` | `integer` | `50` | Giới hạn tối đa số lần gọi LLM trong 1 tác vụ. |
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
Thị trường xe điện tại Việt Nam ghi nhận tốc độ tăng trưởng kép hàng năm đạt 28.5% [1]...

## 2. Phân tích Hạ tầng Trạm Sạc
...

---
## Danh mục Tài liệu Tham khảo
[1] Bộ Công Thương - Báo cáo Phát triển Năng lượng Xanh 2025. URL: https://moit.gov.vn/...
[2] Vietnam EV Market Outlook 2026 - BloombergNEF. URL: https://about.bnef.com/...
```

---

## 📊 Kế hoạch đánh giá (chưa có benchmark được xác minh)

| Chỉ số cần đo | Cách đánh giá |
|---|---|
| Citation integrity | Tỷ lệ citation trỏ tới source/chunk tồn tại và thuộc đúng task. |
| Claim support | Người đánh giá gán nhãn claim/evidence; báo cáo precision/recall hoặc tỷ lệ hỗ trợ trên test set versioned. |
| Coverage/diversity | Mức bao phủ câu hỏi con, loại nguồn, thời gian và quan điểm đối lập. |
| Hiệu năng/chi phí | p50/p95 latency, lỗi, token/cost trên bộ câu hỏi và cấu hình đã ghi. |

Chỉ so sánh với prompting/RAG cơ bản sau khi chạy cùng bộ câu hỏi, nguồn đầu vào, model/budget và rubric đánh giá; không dùng bảng tính năng chủ quan như benchmark.

---

## 🗺️ Lộ trình Phát triển (Roadmap)

Lộ trình chi tiết, thời hạn, phụ trách và trạng thái theo evidence nằm tại [roadmap-and-progress.md](docs/project/roadmap-and-progress.md). Định hướng mở rộng người dùng theo release gates: cá nhân/nhà nghiên cứu trước; chuyên gia và nhiều loại phương pháp sau khi chất lượng được đánh giá; nhóm/tổ chức chỉ sau khi có collaboration, tenant isolation, privacy và operational controls. Đây là định hướng, không phải cam kết phát hành.

Mốc demo 10/11/2026 tập trung một đường literature-review đầu-cuối. Runner chỉ được đưa vào demo nếu routine/dataset hẹp đạt kiểm tra an toàn và tái lập; các research path ngoài hệ thống dừng ở protocol và chờ người dùng. Không mở rộng scope nếu làm giảm thời gian kiểm chứng core path.

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
