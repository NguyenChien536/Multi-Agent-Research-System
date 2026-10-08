# Technical Design — Chức năng, công nghệ và mẫu kiến trúc ATI

**Cập nhật:** 09/10/2026 · **Trạng thái:** quyết định thiết kế cho bản nộp; không phải xác nhận implementation.<br>
**Nguồn yêu cầu:** [SRS v4.1](../requirements/SRS.md) · **Quyết định:** [ADR-004](decisions/ADR-004-multi-agent-research-delivery.md) · **Luồng chuẩn:** [System Design](system-design.md), [User Journey](../project/user-journey-and-outputs.md).

Tài liệu này giúp đọc từ chức năng người dùng tới thành phần xử lý, dữ liệu, technology và design pattern. “Hiện có” nghĩa là thấy trong source tại revision ebb525a; “target” cần implement và đạt gate tương ứng. Dependency phải được pin ở P0 trước khi viết code mới; adapter không được tự đổi provider/model trong lúc chạy.

## 1. Phạm vi chức năng đã chốt

| Chức năng | Hành vi mong đợi | Luồng/thành phần | Pattern chính | Hiện trạng đọc source |
|---|---|---|---|---|
| Tài khoản và workspace riêng | Đăng ký, đăng nhập, chỉ xem task/file của mình | FastAPI auth → owner-scoped service/repository → PostgreSQL | Bearer authentication, authorization by ownership, service/repository | Có đăng ký, password hashing và JWT helper; chưa có login/current-user dependency, research route còn dummy user |
| Tạo nhiều bài và plan | Nhập câu hỏi, ngôn ngữ/loại bài; xem/chỉnh plan và budget; chuyển bài A/B độc lập | API → ResearchTask/ResearchPlan → LangGraph Supervisor | Command/service layer, immutable plan version, policy guard | Có tạo/list task; chưa có plan version, quota RUNNING hoặc multi-task wait/resume đã nghiệm thu |
| Tìm web và nguồn PDF | Search nguồn, safe-fetch nội dung; upload PDF có text và giới hạn owner/size/type | Researcher → Search adapter/fetch; PDF ingest → Source/DocumentChunk | Ports and adapters, ingestion pipeline, dedup/idempotency | Tavily/fetch/chunk/embed có source; PDF upload và full E2E chưa được chứng minh |
| Bằng chứng và gợi ý gap | Xem claim, quote, nguồn/đoạn và ý kiến trái chiều; gap gắn phạm vi tìm kiếm | Evidence Analyst → Evidence/ClaimEvidence/ResearchClaim → Writer/ReportClaim | Provenance/lineage, structured output, deterministic validation | Junction schema có trong source; Analyst chưa lưu đủ UUID/quote chain; validator còn thiếu |
| Research loop | Khi Critic chỉ ra thiếu căn cứ, tìm bổ sung đúng câu hỏi, dừng khi không có nguồn mới/cạn budget | Critic → code router → Researcher → ingestion → Evidence Analyst | Bounded feedback loop, state machine, dedup/no-delta guard | Có macro/micro routing mẫu; chưa có đầy đủ evidence delta, budget, critique toàn bài và stop gate |
| Phương pháp/protocol | Nhận method/hypothesis; protocol đã review là artifact trung gian; lab/khảo sát/thực địa do người dùng làm rồi nạp kết quả thật | Methodologist → Writer/Critic/Validator → WAITING_USER_DATA → resume | Conditional workflow, HITL durable interrupt/resume | Chưa có role/checkpointer/resume hoàn chỉnh |
| Experiment tính toán | Chạy routine được duyệt trên CSV numeric; xem bảng/metrics/plots và provenance | Data Analyst → AnalysisRun → trusted launcher/container → artifacts | Allowlisted strategy, isolated process boundary, immutable manifest | Chưa có runner/AnalysisRun thực tế |
| Bài, hỏi đáp và sửa | `COMPLETED` chỉ với bài báo đủ phần/Results thật; Q&A dựa phiên bản/evidence; sửa giữ bản cũ | Writer → Critic → Validator; Q&A/revision service | Versioned document, evaluator loop, command/idempotency | Có một ResearchReport/task và Writer/Critic sơ khai; chưa có version/Q&A |
| Theo dõi nhiều bài | Dashboard status/stage/next action từng bài; thấy agent role, event, warnings và trạng thái chờ/lỗi | TaskEvent/AgentRun → DB → SSE và polling UI | Durable event log + notification, snapshot/replay | Frontend polling 5s; SSE/API progress chưa được nghiệm thu |
| Export và xóa dữ liệu | Tải Markdown/artifacts có quyền; xóa task chặn truy cập ngay rồi dọn dữ liệu | ArtifactStore → authorized API; tombstone → cleanup worker | Private object abstraction, tombstone/retryable cleanup | ExportArtifact model có; private file flow/delete lifecycle chưa đủ |
| Ảnh minh họa | Bài có thể tự thêm ảnh và người dùng bỏ/tắt ảnh | Source page image → optional Serper adapter → report image association | Optional enrichment/adapter | Ngoài bản nộp; không phải evidence hay experiment chart |

Chiến giữ trách nhiệm implementation, dữ liệu đánh giá, review và các gate kỹ thuật; bằng chứng nào chưa thu thập thì chưa đánh dấu nghiệm thu.

## 2. Công nghệ được chọn

| Lớp | Công nghệ/contract | Lý do và giới hạn |
|---|---|---|
| Web UI | Next.js + React + TypeScript; polling snapshot trước, SSE cho progress khi có event contract | Hợp stack đang có; UI chỉ hiển thị trạng thái quan sát được, không giả phần trăm/chain-of-thought |
| HTTP/API | FastAPI + Pydantic v2, REST JSON, OpenAPI; SSE endpoint có auth/replay | HTTP nhận task nhanh; API không giữ request mở để research/lab chờ |
| Authentication | OAuth2-style Bearer access token bằng JWT helper hiện có, python-jose; bcrypt password hashing; owner check ở mọi query/file/event | Giảm thay đổi với source; chỉ access token trước hạn, chưa cần refresh/session phức tạp |
| Domain/persistence | Python async + SQLAlchemy 2 + Alembic; service/repository contract | Dùng DB transaction cho state changes; migration thử ở DB test sạch |
| Primary/vector DB | PostgreSQL + pgvector | Một nguồn relational/vector giảm vận hành; embedding model/dimension/profile phải pin theo corpus, profile đổi thì reindex |
| Long jobs | Celery worker + Redis broker | Giữ provider/research ngoài request; acknowledge/redelivery có thể lặp nên cần outbox + idempotent consumer/CAS |
| Research orchestration | LangGraph StateGraph, typed state, explicit conditional routing; PostgreSQL checkpointer sau khi pin integration | Hợp loops và durable interrupts; state chứa IDs/counters, không chứa file bytes/toàn corpus |
| Search/fetch | Tavily adapter; HTTPX + Trafilatura/BeautifulSoup cho fetch/extract | Tavily là API search hiện có; fetch phải có network/size/time policy và xử lý nội dung như untrusted |
| LLM/embeddings | Một ModelGateway chọn provider/model từ cấu hình allowlist; source có priority Gemini/OpenAI/Anthropic/Groq và embeddings Gemini/OpenAI | Không gọi provider trực tiếp từ UI; pin model/profile từng run; log usage và giới hạn fallback theo quyền dữ liệu |
| PDF/CSV | PDF: chọn pypdf cho text extraction có giới hạn (không OCR). CSV: pandas + NumPy validation | pypdf trích text PDF có text layer; scan/ảnh không được OCR và PDF phức tạp phải báo lỗi/chất lượng thấp. Parser chạy nền; type/page/row/column/size/time limits |
| Analysis | scikit-learn + pandas/NumPy + Matplotlib trong image runner riêng | Regression routine cố định; không dùng RAG để tính số; API/Celery không execute LLM-generated shell/Python |
| Artifact files | ArtifactStore interface; private local volume cho demo, DB giữ key/checksum/owner; API stream file đã authorize | Giữ file bytes ngoài PostgreSQL; adapter cho S3-compatible sau này |
| Observability | Python structured JSON logs + DB AgentRun/TaskEvent; UI polling/SSE | Không thêm telemetry vendor/service; OpenTelemetry/LangSmith tùy chọn sau khi privacy/redaction rõ |
| Runtime | Docker Compose: API, Celery worker, PostgreSQL/pgvector, Redis | Deployment dev hiện có, không tự gọi production; runner job là container boundary riêng, operator launcher được tin cậy và không public |

**Pinning P0:** đồng bộ local/backend/runner Python; khóa tương thích FastAPI/Pydantic/SQLAlchemy/LangGraph/checkpointer/Celery/Redis/provider SDKs/scikit-learn/Pandas; lưu lock và image digest. Không pin model name động theo “latest”. Chọn versions từ clean install thực; tài liệu không đoán số version.

## 3. Mẫu thiết kế áp dụng

| Pattern | Dùng ở đâu | Quy tắc thực thi |
|---|---|---|
| Modular monolith | Một backend codebase, process API và worker tách | Module chia theo auth/task/research/evidence/artifact; agent không là network service riêng |
| Ports and adapters (Hexagonal) | Model/search gateway, embedding gateway, ArtifactStore, AnalysisAdapter | Node gọi interface; fake adapter cho checks; credentials và SDK chỉ ở adapter |
| Orchestrator + explicit state machine | LangGraph điều phối bảy roles; code quyết định chuyển trạng thái | LLM tạo structured result/verdict; guard code kiểm plan/status/budget trước edge và side effect |
| Shared typed workflow state | LangGraph state chứa task/run IDs, plan refs, evidence/artifact IDs, counters | Node trả delta bất biến; reducer có chủ ý; không nối outputs lặp hoặc sửa list tích lũy ngầm |
| Durable HITL interrupt/resume | Duyệt plan hoặc chờ lab/user data | PostgreSQL checkpointer + stable thread/run ID; worker trả khi interrupt; resume kiểm owner/checkpoint/version/file READY |
| Transactional outbox + idempotent consumer | Ghi run/decision và dispatch Celery | Cùng DB transaction lưu outbox; dispatcher claim/retry; worker lease/CAS/output unique. At-least-once, không exactly-once provider call |
| Optimistic concurrency (CAS) + lease | Start/resume/cancel/worker claim | Version/state condition chống double start và stale worker; WAITING vẫn là active run trong task nhưng không giữ worker/quota RUNNING; tối đa 2 RUNNING/user |
| Provider gateway + budget decorator | Mọi search/LLM/embedding call, retry, fallback, Q&A | Reserve trước, call qua gateway, reconcile sau; không thể thu hồi request provider đã nhận |
| Immutable versioned records | Plan/report/revision/analysis manifest | Bản mới append version; Q&A gắn report version; thay data/method vô hiệu hóa kết quả cũ |
| Article template strategy | REVIEW / EMPIRICAL_COMPUTATIONAL / EMPIRICAL_HUMAN | Mỗi loại có section schema, completion gate và provenance rules riêng; lựa chọn template ở plan version, không lấy một dàn ý chung rồi đổi nhãn |
| Provenance graph + deterministic validator | Claims/citations/evidence/analysis artifacts | Kiểm FK/ownership/task/quote/manifest bằng code; FK không chứng minh semantic truth |
| Bounded evaluator/research loop | Critic → targeted search hoặc Writer revision | Tối đa 3 collection rounds gồm lần đầu, 2 revisions sau draft; no-evidence-delta dừng; budget/cancel áp dụng mọi vòng |
| Tombstone + retryable cleanup | Xóa task khi còn job/file/checkpoint | Thu hồi quyền/resume ngay; late output không persist; dọn storage/index/checkpoint có retry trong deadline SRS |

Không dùng event sourcing toàn hệ thống: DB relational lưu domain state hiện hành; TaskEvent là event log phục vụ timeline/replay, không là nguồn duy nhất để tái tạo state.

## 4. Deployment boundaries và quyền dữ liệu

~~~text
Browser
  └─ HTTPS → FastAPI
                ├─ PostgreSQL (domain state + checkpoint + event + outbox)
                ├─ Redis → Celery/LangGraph worker
                ├─ private ArtifactStore
                └─ provider adapters → Tavily / web / allowlisted LLM+embedding

Trusted operator analysis launcher
  └─ creates one constrained Docker container per approved routine
       ├─ read-only input staging + bounded output
       ├─ non-root, read-only root filesystem, no network, resource/time cap
       └─ returns manifest/artifact IDs to AnalysisAdapter
~~~

Launcher là trust boundary vận hành riêng; không public endpoint, không cho API/worker Docker socket, chỉ nhận routine ID/image/config/schema allowlist. Giới hạn Docker dành cho routine do dự án kiểm soát; không chứng nhận arbitrary hostile code an toàn. Nếu tương lai chạy mã do model sinh, phải chọn sandbox/threat model mới (managed sandbox/MicroVM/gVisor) trước.

Flow target của ba output types ở [System Architecture HLD](system-architecture.md); diagram chuẩn nằm tại [System Design](system-design.md).

## 5. Ràng buộc hợp đồng và trạng thái

- ResearchTask là workspace của một bài; một user có nhiều task độc lập. ResearchRun là lần execute/revise. status lifecycle độc lập stage.
- Tạo task trả 201; start/resume trả 202 khi run/outbox đã commit. Route hiện tại còn contract cũ, phải thay và đồng bộ UI.
- Một active run/task bao gồm WAITING_APPROVAL/WAITING_USER_DATA; A chờ không chặn B. RUNNING/user cap ở dispatcher/worker; QUEUED có outbox bền vững. Sửa plan đúng version giữ run/counters/budget; sửa report sau terminal tạo ResearchRun mới.
- COMPLETED chỉ khi bài báo đúng loại có đủ sections, Results thật khi cần và technical lineage gates đạt. Protocol/biểu mẫu là trung gian; PARTIAL công khai phần thiếu và giữ lineage hợp lệ; NEEDS_REVIEW giữ output không phát hành như bản hoàn tất.
- Report/Q&A/revision/delete/upload mọi route phải owner-check. Xóa task tombstone chặn read/resume/late writes trước cleanup.
- External content/file không tin cậy; không cho nội dung nguồn gọi tool hoặc thay đổi policy.
- Full requirements và budget defaults ở [SRS](../requirements/SRS.md); state/API transitions ở [Data Model & API](../technical/data-model-and-api.md).

## 6. Không thuộc design hiện hành

- Mỗi agent thành microservice, Kafka/Kubernetes, DB vector riêng, long-term unconstrained memory.
- Chạy mã do LLM sinh tùy ý trong API/worker hoặc trong runner của bản nộp.
- Tuyển người, làm khảo sát/lab ngoài ATI, tự xác nhận ethics/consent.
- Khẳng định candidate gap là novelty toàn ngành; gọi Critic là peer review.
- Ảnh minh họa như evidence; biểu đồ experiment bị lẫn với ảnh ngoài.
- Gọi target là production-ready hoặc claim chất lượng chưa được đánh giá.

## 7. Tham khảo kỹ thuật

- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Celery — Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [C4 Model — Container](https://c4model.com/diagrams/container)
- [pypdf — Extract text from a PDF](https://pypdf.readthedocs.io/en/latest/user/extract-text.html): text extraction, không phải OCR.
- [Docker — Security](https://docs.docker.com/engine/security/)
- [scikit-learn — Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)

\n
