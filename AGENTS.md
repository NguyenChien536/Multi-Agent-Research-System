# 🛡️ AGENTS.md — Quy tắc Vận hành AI cho Multi-Agent Research System

> **Tệp này được mọi AI Coding Assistant (Antigravity, Cursor, Claude Code, GitHub Copilot)
> tự động nạp vào đầu mỗi phiên làm việc.**
> Mục đích: Ép buộc AI tuân thủ kiến trúc, quy chuẩn kỹ thuật và quy trình phát triển
> chuẩn Principal Engineer cho toàn bộ dự án.

---

## 1. TỔNG QUAN DỰ ÁN (PROJECT CONTEXT)

### 1.1 Mô tả Sản phẩm
Multi-Agent Research System là nền tảng nghiên cứu tự động chuyên sâu sử dụng
kiến trúc Đa Tác tử (Multi-Agent System) phối hợp với Vector Database (RAG) và
Quy trình Phản biện Độc lập (Critic Loop).

Người dùng nhập một đề tài → Hệ thống tự động hóa toàn bộ quy trình nghiên cứu
qua 5 Agent AI chuyên biệt → Xuất bản báo cáo chuyên sâu có trích dẫn nguồn chuẩn
học thuật (Markdown & PDF).

### 1.2 Kiến trúc Tổng quan
```
Client (Next.js 14)
  ↓ HTTP / SSE
API Gateway (FastAPI + Pydantic v2)
  ↓ Celery Task Queue
LangGraph Multi-Agent Engine (Celery Worker)
  ├── Supervisor Agent   → Lập đề cương, routing, điều phối Dual-loop
  ├── Researcher Agent   → Tavily Search API + asyncio.gather song song
  ├── Curator Module     → URL dedup, Chunking, Vector embedding
  ├── Analyst Agent      → Semantic Search (RAG) trên pgvector
  ├── Writer Agent       → Biên soạn báo cáo từ Claims/Evidence
  ├── Critic Agent       → Phản biện, kiểm chứng (Micro-loop & Macro-loop)
  └── Post-Processor     → Đánh số citation bằng regex deterministic
  ↓
PostgreSQL 16 + pgvector (Long-term Memory / Vector Store)
Redis 7 (Celery Broker + SSE Pub/Sub + Rate Limiter)
```

### 1.3 Tech Stack Cố định (KHÔNG ĐƯỢC THAY ĐỔI)
| Tầng | Công nghệ | Phiên bản tối thiểu |
|------|-----------|---------------------|
| Backend Framework | FastAPI | ≥ 0.111.0 |
| Validation | Pydantic v2 | ≥ 2.7.0 |
| ORM | SQLAlchemy 2.0 (Async) | ≥ 2.0.30 |
| Database | PostgreSQL 16 + pgvector | pg16, pgvector ≥ 0.2.5 |
| Async DB Driver | asyncpg | ≥ 0.29.0 |
| Migration | Alembic | ≥ 1.13.1 |
| Task Queue | Celery 5 + Redis 7 | Celery ≥ 5.4.0 |
| AI Orchestration | LangGraph | ≥ 0.1.0 |
| AI Framework | LangChain | ≥ 0.2.0 |
| LLM Providers | OpenAI (GPT-4o) / Anthropic (Claude 3.5) | langchain-openai ≥ 0.1.7 |
| Search API | Tavily | tavily-python ≥ 0.3.3 |
| Web Scraping | Trafilatura + BeautifulSoup4 | trafilatura ≥ 1.9.0 |
| HTTP Client | httpx (Async) | ≥ 0.27.0 |
| Realtime | SSE (sse-starlette) | ≥ 2.1.0 |
| Embedding | OpenAI text-embedding-3-small | 1536 dimensions |
| Observability | OpenTelemetry + LangSmith | — |
| Container | Docker Compose | 4 services |

---

## 2. QUY TRÌNH PHÁT TRIỂN BẮT BUỘC (DEV-LIFECYCLE)

**Với MỌI yêu cầu (thêm tính năng, sửa lỗi, refactor), bạn BẮT BUỘC thực hiện
theo 4 pha tuần tự. KHÔNG ĐƯỢC bỏ qua bất kỳ pha nào.**

### Pha 1: 🔍 PHÂN TÍCH & THIẾT KẾ (Requirements & Architecture)
1. **Xác định phạm vi thay đổi:** Liệt kê cụ thể các tầng bị tác động:
   - Tầng API (`backend/app/api/v1/endpoints/`)
   - Tầng Schema (`backend/app/schemas/`)
   - Tầng Model/DB (`backend/app/models/`)
   - Tầng Agent/LangGraph (`backend/app/agents/`)
   - Tầng Tools (`backend/app/tools/`)
   - Tầng Worker (`backend/app/worker.py`)
   - Tầng Config (`backend/app/core/`)
2. **Trình bày phương án thiết kế** ngắn gọn (3-5 bullet points) TRƯỚC khi viết code.
3. **Kiểm tra tương thích:** Đảm bảo thay đổi không phá vỡ LangGraph State,
   Schema validation, hoặc Database migration hiện tại.

### Pha 2: 🏗️ TRIỂN KHAI (Implementation)
1. **Viết Schema/Interface trước, Logic sau:**
   - Luôn định nghĩa Pydantic schema đầu vào/đầu ra trước.
   - Sau đó mới viết hàm xử lý logic.
2. **Code phải hoàn chỉnh, không bỏ dở:**
   - TUYỆT ĐỐI KHÔNG viết: `# TODO: implement later`, `# ... rest of logic`,
     `pass  # placeholder`, hoặc bất kỳ stub/placeholder nào.
   - Nếu logic phức tạp, hãy chia nhỏ thành nhiều hàm helper có tên rõ ràng.
3. **Tuân thủ toàn bộ Code Standards ở Mục 3 bên dưới.**

### Pha 3: ✅ XÁC MINH (Verification)
1. **Viết test hoặc lệnh kiểm thử:**
   - Với API endpoint: Cung cấp lệnh `curl` hoặc `httpie` mẫu chạy được.
   - Với hàm logic: Cung cấp unit test (`pytest`) hoặc script Python mẫu.
   - Với LangGraph node: Cung cấp mock state input/output để kiểm tra.
2. **Kiểm tra lỗi cú pháp và typing:** Code phải pass `mypy` / type checking cơ bản.
3. **Chỉ coi là HOÀN THÀNH khi có bằng chứng xác minh kết quả chạy thật.**

### Pha 4: 📋 BÀN GIAO (Structured Summary)
Kết thúc mỗi task, trình bày tóm tắt theo format:
```
### Tóm tắt Thay đổi
- **Files đã tạo mới:** [danh sách]
- **Files đã chỉnh sửa:** [danh sách]
- **Breaking changes:** [có/không, mô tả nếu có]
- **Cần migration DB:** [có/không]
- **Lệnh kiểm thử:** [curl / pytest command]
```

---

## 3. QUY CHUẨN KỸ THUẬT BẤT BIẾN (CODE STANDARDS)

### 3.1 Python & Async — Quy tắc Vàng
```python
# ✅ ĐÚNG — Luôn dùng async
async def get_research_task(task_id: uuid.UUID, db: AsyncSession):
    result = await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))
    return result.scalar_one_or_none()

# ❌ SAI — Tuyệt đối KHÔNG dùng blocking I/O
def get_research_task(task_id, db):  # thiếu async
    import requests                  # thư viện blocking
    response = requests.get(url)     # chặn event loop
    time.sleep(1)                    # chặn event loop
```

**Các thư viện BỊ CẤM (Blocking):**
- `requests` → Thay bằng `httpx.AsyncClient`
- `time.sleep()` → Thay bằng `asyncio.sleep()`
- `psycopg2` trực tiếp → Luôn dùng qua `asyncpg` + SQLAlchemy async
- `urllib`, `urllib3` → Thay bằng `httpx`

### 3.2 SQLAlchemy 2.0 Modern Style
```python
# ✅ ĐÚNG — SQLAlchemy 2.0 select() style
from sqlalchemy import select
result = await db.execute(
    select(ResearchTask)
    .where(ResearchTask.status == "PENDING")
    .order_by(ResearchTask.created_at.desc())
    .offset(skip).limit(limit)
)
tasks = result.scalars().all()

# ❌ SAI — SQLAlchemy 1.x legacy style
tasks = db.query(ResearchTask).filter_by(status="PENDING").all()
```

### 3.3 Pydantic v2 Strict
```python
# ✅ ĐÚNG — Pydantic v2 API
class ResearchTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str

data = task_response.model_dump()           # v2
obj = ResearchTaskResponse.model_validate(db_obj)  # v2

# ❌ SAI — Pydantic v1 deprecated API
class ResearchTaskResponse(BaseModel):
    class Config:
        orm_mode = True          # v1 deprecated

data = task_response.dict()                 # v1 deprecated
obj = ResearchTaskResponse.from_orm(db_obj) # v1 deprecated
```

### 3.4 LangGraph State & Graph Conventions
```python
# ✅ ĐÚNG — State Reducers bảo toàn dữ liệu tích lũy
class ResearchState(TypedDict):
    collected_sources: Annotated[list, operator.add]     # Tích lũy, không ghi đè
    visited_urls: Annotated[set, merge_sets]              # Tích lũy, không ghi đè
    claims: Annotated[list, operator.add]                 # Tích lũy, không ghi đè
    evidences: Annotated[list, operator.add]              # Tích lũy, không ghi đè
    errors: Annotated[list, operator.add]                 # Tích lũy, không ghi đè

# ❌ SAI — Ghi đè State làm mất dữ liệu vòng lặp trước
def researcher_node(state: ResearchState) -> dict:
    return {"collected_sources": new_sources}  # MẤT toàn bộ sources cũ nếu không dùng reducer
```

**Quy tắc LangGraph:**
- Mỗi Node function nhận `state: ResearchState` và trả về `dict` chứa các field cần update.
- Các field tích lũy (lists, sets) PHẢI dùng `Annotated` reducer (`operator.add`, `merge_sets`).
- Các field ghi đè (scalar: `status`, `draft_report`, `current_agent`) KHÔNG cần reducer.
- Graph definition trong `graph.py` dùng `StateGraph(ResearchState)`.
- Routing logic (Supervisor) phải là **code Python deterministic**, KHÔNG gọi LLM để quyết định routing.

### 3.5 FastAPI Endpoint Conventions
```python
# ✅ Chuẩn mực endpoint
@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_research_task(
    task_in: ResearchTaskCreate,           # Pydantic v2 schema validation
    db: AsyncSession = Depends(get_db),    # Async session DI
):
    """Tạo mới một Research Task."""       # Docstring tiếng Việt ngắn gọn
    # Logic...
    return task
```

**Quy tắc API:**
- Mọi endpoint phải khai báo `response_model` rõ ràng.
- Dependency injection qua `Depends(get_db)` cho database session.
- HTTP status code phải chính xác (201 cho POST tạo mới, 200 cho GET, 404 cho not found).
- Xử lý lỗi bằng `HTTPException` với `status_code` và `detail` cụ thể.

### 3.6 Database Model Conventions
```python
# ✅ Chuẩn mực SQLAlchemy model
class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Quy tắc Database:**
- Primary key luôn là `UUID`, không dùng auto-increment integer.
- Mọi bảng phải có `created_at` và `updated_at` với timezone.
- Index các cột thường xuyên query: `status`, `user_id`, `task_id`.
- Khi thêm bảng/cột mới, phải nhắc nhở tạo Alembic migration.

---

## 4. CẤU TRÚC THƯ MỤC & FILE NAMING

```
backend/app/
├── agents/               # LangGraph Engine
│   ├── state.py          # ResearchState TypedDict + Reducers
│   ├── nodes.py          # Tất cả Node functions (supervisor, researcher, analyst, ...)
│   └── graph.py          # StateGraph definition + Compile
├── api/v1/
│   ├── api.py            # Router aggregator
│   └── endpoints/
│       ├── health.py     # GET /health
│       ├── research.py   # CRUD + Start workflow
│       └── stream.py     # SSE streaming endpoint (tương lai)
├── core/
│   ├── config.py         # Settings (pydantic-settings, .env loading)
│   ├── database.py       # AsyncEngine, AsyncSession, get_db()
│   └── security.py       # JWT, hashing (tương lai)
├── db/
│   └── session.py        # Nơi quản lý session factory (nếu tách riêng)
├── models/
│   ├── base.py           # declarative_base()
│   ├── task.py           # ResearchTask
│   ├── source.py         # Source / WebPage (tương lai)
│   ├── chunk.py          # DocumentChunk + vector embedding (tương lai)
│   ├── claim.py          # ResearchClaim (tương lai)
│   └── evidence.py       # Evidence (tương lai)
├── schemas/
│   ├── task.py           # ResearchTaskCreate, ResearchTaskResponse, ResearchBudget
│   ├── source.py         # (tương lai)
│   └── report.py         # (tương lai)
├── tools/
│   ├── search.py         # Tavily Search wrapper
│   ├── scraper.py        # Web scraper + SSRF Guard (tương lai)
│   └── embedder.py       # Embedding + pgvector upsert (tương lai)
├── main.py               # FastAPI app factory
└── worker.py             # Celery app + task definitions
```

**Quy tắc đặt tên:**
- File name: `snake_case.py` (ví dụ: `research_task.py`, `document_chunk.py`)
- Class name: `PascalCase` (ví dụ: `ResearchTask`, `DocumentChunk`)
- Function name: `snake_case` (ví dụ: `create_research_task`, `supervisor_node`)
- Constant: `UPPER_SNAKE_CASE` (ví dụ: `MAX_RETRY_COUNT`, `DEFAULT_CHUNK_SIZE`)

---

## 5. KIẾN TRÚC ĐA TÁC TỬ — NGUYÊN TẮC THIẾT KẾ

### 5.1 Luồng Xử lý Chuẩn (Research Pipeline)
```
User Input → Supervisor (Lập đề cương)
  → [HITL: Người dùng duyệt đề cương nếu require_plan_approval=True]
  → Researcher (Tavily search song song + cào web)
  → Curator (URL dedup + Chunking + Vector embedding vào pgvector)
  → Analyst (Semantic Search RAG → trích xuất Claims + Evidence)
  → Writer (Biên soạn draft báo cáo)
  ⟷ Critic (Micro-loop: tối đa 2 vòng sửa bài)
  → [Nếu Critic phát hiện thiếu dữ liệu → Macro-loop: quay lại Supervisor sinh Delta Queries]
  → Post-Processor (Đánh số citation [1], [2] bằng regex)
  → Final Report (Markdown + PDF)
```

### 5.2 Quy tắc Vòng lặp
- **Micro-loop (Writer ⟷ Critic):** Tối đa `2` vòng. Dùng `micro_loop_count` trong State để đếm.
- **Macro-loop (Supervisor ⟷ Researcher):** Tối đa `max_iterations` vòng (mặc định 2).
  Dùng `iteration_count` trong State để đếm.
- **Budget Guardrail:** Kiểm tra `budget_config.max_llm_calls` và `budget_config.max_cost_usd`
  trước mỗi lần gọi LLM. Vượt ngưỡng → dừng ngay, ghi lỗi vào `errors`.

### 5.3 Nguyên tắc Chống Ảo giác (Zero-Hallucination)
- Mọi trích dẫn (citation) PHẢI được neo giữ (grounding) từ `DocumentChunk` thực tế trong pgvector.
- Đánh số trích dẫn bằng **code Python regex deterministic**, KHÔNG để LLM tự sinh link.
- Curator module phải kiểm tra URL có thực sự trả về nội dung hợp lệ (HTTP 200) trước khi lưu.

### 5.4 Nguyên tắc Supervisor Routing
- Quyết định routing (chuyển sang Agent nào tiếp theo) phải bằng **code logic Python if/else**,
  KHÔNG gọi LLM để quyết định routing (LLM chỉ dùng để sinh nội dung: queries, analysis, draft).

### 5.5 Tối ưu Hiệu năng (Performance & Tiered Models)
Để ép tổng thời gian 1 vòng lặp xuống dưới 30s, bắt buộc tuân thủ:
- **Tiered Models:** Dùng `GPT-4o-mini`, `Claude 3.5 Haiku` hoặc `Gemini 1.5 Flash` cho Supervisor, Analyst và Critic. Dành mô hình xịn nhất (`GPT-4o`, `Claude 3.5 Sonnet`) cho Writer.
- **Parallel Analyst:** Dùng `asyncio.gather()` khi Analyst đọc nhiều DocumentChunk. KHÔNG chạy tuần tự (for-loop chặn I/O).
- **Zero-Latency UX:** Frontend nhận text của Writer qua Server-Sent Events (SSE). Backend KHÔNG chờ Writer sinh xong mới trả kết quả.
- **Strict JSON Critic:** Ép Critic trả về format JSON siêu ngắn (VD: `{"verdict": "REVISE", "feedback": "..."}`) để giảm số output tokens, tăng tốc độ phản hồi.

### 5.6 Xuất bản Đa định dạng
Mọi Research Task hoàn thành phải hỗ trợ xuất bản ra các định dạng chuẩn học thuật:
- **Markdown (.md):** Dùng trực tiếp từ Writer.
- **Word (.docx):** Dùng thư viện `python-docx` để giữ nguyên bảng biểu, format.
- **PDF (.pdf):** Dùng `WeasyPrint` dàn trang A4, Header/Footer, tự động sinh Mục lục (ToC).
- *(Tùy chọn)* **LaTeX (.tex):** Xuất qua Pandoc cho mục đích nhúng bài báo quốc tế.

---

## 6. NGUYÊN TẮC BẢO MẬT

- **SSRF Guard:** Mọi URL trước khi fetch phải qua bộ lọc: chặn IP private (10.x, 172.16.x, 192.168.x),
  chặn localhost, chặn schema file:// và ftp://.
- **Prompt Injection:** Nội dung web cào về phải được sanitize trước khi nạp vào prompt LLM.
  Không bao giờ đưa raw HTML vào prompt.
- **API Keys:** Tất cả secrets lưu trong `.env`, KHÔNG ĐƯỢC hardcode trong code.
  File `.env` đã nằm trong `.gitignore`.
- **CORS:** Chỉ cho phép origins được khai báo trong `BACKEND_CORS_ORIGINS`.

---

## 7. DOCKER & DEPLOYMENT

### 7.1 Docker Compose Services
| Service | Image | Port | Vai trò |
|---------|-------|------|---------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | CSDL chính + Vector Store |
| `redis` | `redis:7-alpine` | 6379 | Celery Broker + SSE Pub/Sub |
| `backend` | Build từ `./backend/Dockerfile` | 8000 | FastAPI API Gateway |
| `worker` | Cùng image với backend | — | Celery Worker chạy LangGraph |

### 7.2 Quy tắc Docker
- Không thêm service mới vào `docker-compose.yml` khi chưa được phê duyệt.
- Mọi biến môi trường mới phải được thêm vào CẢ `.env.example` và `backend/app/core/config.py`.
- Health check bắt buộc cho mọi service.

---

## 8. NGÔN NGỮ & GIAO TIẾP

- **Comment trong code:** Tiếng Việt hoặc Tiếng Anh đều được, ưu tiên Tiếng Việt cho comment
  giải thích logic nghiệp vụ, Tiếng Anh cho docstring và comment kỹ thuật.
- **Docstring API:** Tiếng Việt ngắn gọn (ví dụ: `"""Tạo mới một Research Task."""`).
- **Commit message:** Tiếng Anh, theo Conventional Commits
  (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
- **Biến, hàm, class:** Tiếng Anh 100%.

---

## 9. DANH SÁCH KIỂM TRA NHANH (QUICK CHECKLIST)

Trước khi hoàn thành bất kỳ task nào, tự kiểm tra:

- [ ] Đã phân tích phạm vi thay đổi (Pha 1)?
- [ ] Code 100% async (không có blocking I/O)?
- [ ] SQLAlchemy dùng `select()` style 2.0 (không dùng `db.query()`)?
- [ ] Pydantic dùng `model_dump()` / `model_validate()` (không dùng `.dict()` / `.from_orm()`)?
- [ ] LangGraph State update dùng reducer cho list/set fields?
- [ ] Không có placeholder / TODO / stub code?
- [ ] Có lệnh kiểm thử (curl / pytest) kèm theo?
- [ ] Secrets không bị hardcode?
- [ ] Có tóm tắt bàn giao (Pha 4)?

---

## 10. QUY TRÌNH GIT VÀ PHỐI HỢP CODEX / ANTIGRAVITY

- Quy trình dùng GitHub Flow gọn nhẹ: `main` là nhánh ổn định; mỗi Issue/tính năng có một branch riêng và Pull Request về `main`.
- Không triển khai trực tiếp trên `main`; không gộp nhiều mục tiêu không liên quan vào cùng branch/PR.
- Trước mỗi task, đọc `.agents/skills/feature-delivery/SKILL.md` cùng GitHub Issue và kiểm tra trạng thái working tree.
- Khi người dùng yêu cầu một task triển khai cụ thể mà chưa có Issue, tìm Issue đang mở trùng mục tiêu; nếu chưa có thì tự tạo GitHub Issue với phạm vi và tiêu chí nghiệm thu suy ra từ yêu cầu. Không tạo Issue cho câu hỏi, review hay tư vấn thuần túy.
- Codex là lựa chọn ưu tiên để lập kế hoạch/review khi khả dụng. Antigravity là agent triển khai chính. Nếu Codex hết quota/không khả dụng, Antigravity tự khảo sát, lập kế hoạch, triển khai và tự review dựa trên cùng Issue, file hướng dẫn và trạng thái Git.
- Lưu quyết định, kế hoạch và kết quả xác minh trong GitHub Issue/PR hoặc file được commit; không để thông tin bàn giao chỉ nằm trong lịch sử chat.
- Agent không tự merge PR, push thay người dùng, deploy, xóa dữ liệu, hoặc thực hiện thao tác phá hủy. Người dùng duyệt PR và quyết định merge.
- Sau tối đa 3 vòng sửa/review, nếu vẫn còn lỗi hoặc cần đổi API, database, bảo mật hay kiến trúc, dừng và báo người dùng để quyết định.
- Tạo branch bằng `scripts/new-feature-branch.ps1` sau khi Issue có phạm vi và tiêu chí nghiệm thu. Script yêu cầu working tree sạch và tạo branch từ `origin/main`.
- Tên branch: `feature/<issue>-<slug>`, `fix/<issue>-<slug>`, `docs/<issue>-<slug>`, hoặc `chore/<issue>-<slug>`.
- Commit theo Conventional Commits. PR phải liên kết Issue và ghi rõ thay đổi, lệnh đã chạy, kết quả, phần chưa xác minh và rủi ro còn lại.
