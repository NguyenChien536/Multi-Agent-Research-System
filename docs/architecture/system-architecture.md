# System Architecture — High-Level Design

**Cập nhật:** 06/10/2026 · **Trạng thái:** kiến trúc mục tiêu, chưa phải deployment đã nghiệm thu.

## 1. Mục đích

ATI là research orchestrator có AI hỗ trợ và người dùng kiểm soát. HLD giải thích boundary, container và các quyết định vận hành ở mức cao; [system-design.md](system-design.md) là nguồn chuẩn cho sơ đồ C4 Container, DFD, inference flow, async sequence, ERD, Physical DFD và class view. [SRS](../requirements/SRS.md) là nguồn chuẩn yêu cầu sản phẩm.

## 2. Boundary và actors

- Người dùng tạo câu hỏi, thêm paper/dataset được phép, xem quá trình, phản hồi kế hoạch, cung cấp kết quả từ hoạt động ngoài hệ thống, và kiểm tra bài báo.
- ATI chịu trách nhiệm điều phối, truy xuất provenance, lưu checkpoint và hiển thị giới hạn.
- Search, public web, LLM/embedding và optional image search là providers ngoài. Mỗi request phải có budget, timeout, usage log và xử lý nội dung không tin cậy.
- Lab, khảo sát, fieldwork và tuyển người nằm ngoài hệ thống. ATI chỉ hỗ trợ protocol; nghiên cứu viên chịu trách nhiệm review/approval và thực hiện.
- Người dùng chịu trách nhiệm bảo đảm quyền được phép tải lên dữ liệu. ATI phải có file validation, access control, retention và deletion policy.

## 3. Containers và luồng chính

| Container | Trách nhiệm | Boundary/Trade-off |
|---|---|---|
| Next.js Web UI | Tạo task, upload, progress, review, report, export | SSE mục tiêu, polling fallback; hiển thị rõ WAITING_USER_DATA |
| FastAPI | Auth/ownership, task lifecycle, file access, approvals, resume, reports | HTTP requests ngắn; API không chạy research dài |
| Redis | Celery queue và progress events | Không là source of truth; trạng thái bền vững ở DB |
| Celery + LangGraph worker | Điều phối nodes/loops, provider calls, citation lineage | Retry/idempotency và checkpoint phải thiết kế; worker không thực thi arbitrary code |
| PostgreSQL + pgvector | Relational state, source/chunk/vector/evidence/report/run metadata | Giảm dịch vụ cho MVP; index/tenant constraints cần benchmark |
| Object storage | PDF, datasets, protocols/exports/charts | DB lưu metadata/checksum/owner, không chứa file bytes; URL phải được authorize |
| Isolated analysis runner | Chạy routine phân tích được duyệt trong resource boundary | Công nghệ provider/build chưa chốt; ADR + threat model là gate |
| Observability | Structured logs, metrics, trace/correlation IDs | Bắt đầu với logs/metrics; OTel/dashboard khi ngân sách/triển khai cho phép |

## 4. Research workflow target

1. Supervisor phân loại task, dựng plan, report type và budget; user approval là tùy chọn theo cấu hình.
2. Researcher/Curator tìm, tải và chuẩn hóa nguồn web hoặc tài liệu user.
3. Evidence Analyst tổng hợp claim, quote, source/chunk lineage, mâu thuẫn và giới hạn.
4. Synthesis node trình bày candidate questions/gaps theo phạm vi tìm kiếm, không khẳng định toàn diện.
5. Methodology Designer đề xuất hypothesis, phương pháp, protocol và data plan.
6. Với computational research, chỉ chạy routine hỗ trợ trên dữ liệu đã validate trong isolated runner. Kết quả bảng/biểu đồ phải gắn lại input artifact và routine/config/version.
7. Với lab/survey/field/human participant, xuất protocol + ethics notice; persist WAITING_USER_DATA và kết thúc worker job. Sau khi user nạp kết quả được phép, enqueue job mới để resume.
8. Writer sinh đúng template loại nghiên cứu; Critic kiểm tra method/evidence/completeness; bounded loops; validator kiểm tra citation/artefact lineage.
9. Chỉ tạo empirical Results từ actual data. Khi thiếu nguồn hoặc dữ liệu, trả draft/protocol/partial với giới hạn được nói rõ.

Chi tiết flow tại [system-design.md §4](system-design.md#4-inference-flow--multi-agent-workflow).

## 5. Reliability, safety, and data integrity

- Checkpoint, task state và user decision phải lưu bền vững; không giữ worker/HTTP connection trong thời gian user đi thực hiện nghiên cứu.
- Mọi side-effect khi resume phải idempotent; định danh job/checkpoint rõ; lỗi provider có retry hữu hạn.
- Các vòng: macro research tối đa 3 iteration, dừng sớm khi không thêm evidence; micro revision có max count; mỗi external provider call kiểm tra token/cost/time budget.
- SSRF-safe fetch; file type/magic-byte/size limits; untrusted prompt isolation; secrets redaction; per-user ownership.
- Runner không nhận arbitrary code mặc định; network blocked, CPU/memory/time quota, non-root/read-only filesystem tùy công nghệ.
- Human-subject workflow không khởi động tuyển người/nghiên cứu; protocol là bản nháp cần review của tổ chức.
- Research logs không lưu raw uploads/secrets; lưu task_id/correlation_id, agent/node, status, duration, retries, provider usage, artifact IDs và redacted error.
- Citation integrity (quan hệ kỹ thuật) được báo cáo riêng với semantic support (đánh giá nội dung).

## 6. Quyết định công nghệ và trade-offs

| Chọn lựa | Lý do | Chi phí/rủi ro | Quy tắc giảm thiểu |
|---|---|---|---|
| LangGraph | Graph/state/checkpoint hợp với loop và pause/resume | Tăng độ phức tạp; state/reducer cần test | Giữ node/schema nhỏ; test routing không gọi provider |
| Celery + Redis | Tách tác vụ dài khỏi HTTP | Retry/queue/state có thể lệch DB | DB là source of truth; idempotency và reconciliation |
| PostgreSQL + pgvector | Một DB cho metadata và retrieval | Vector workload có thể ảnh hưởng relational query | Đặt task filter/index, benchmark trước khi tách vector DB |
| LLM providers | Tạo/tổng hợp ngôn ngữ, structured output | Cost, latency, hallucination, privacy | Guardrails, bounded loops, log usage, validate output |
| Isolated runner | Ngăn mã/data analysis ảnh hưởng app/worker | Khó thiết lập bảo mật và vận hành | Chỉ routines được duyệt; ADR chọn managed sandbox hoặc restricted service |
| SSE/polling | Cập nhật tiến độ dài hạn | SSE cần reconnect/replay/authorization | DB lưu latest state; SSE chỉ là delivery, polling fallback |
| Object storage | File lớn không phù hợp DB | Cần access/retention policy | Private bucket, signed/authorized downloads, checksum |

## 7. Release boundaries

**Demo đến 10/11/2026:** ưu tiên một workflow research review end-to-end có source upload + web, candidate gap có giới hạn, citation/provenance, progress/monitoring và một analysis slice nhỏ nếu runner/analyzer đạt an toàn. Các phương pháp ngoài phạm vi analysis được hỗ trợ dừng ở protocol hoặc nhận data do user xử lý. Không hứa hỗ trợ toàn bộ chuẩn ngành.

**Target sau demo:** mở thêm type-specific article templates và methods, durable human-data resume, analysis routines, image/PDF exports, evaluation, access control/privacy hardening. Mỗi phần chỉ được đánh dấu release sau acceptance evidence.

## 8. Implementation evidence

Runtime evidence gần nhất là [baseline-verification.md](../project/baseline-verification.md), cập nhật 28/09 từ lượt chạy 27/09. FastAPI health/task smoke checks, Docker services, PostgreSQL/pgvector, Redis/Celery ping và graph compile/routing đã được kiểm tra. Research E2E, auth/ownership, SSE, upload, checkpoints, analysis runner, citation validator và report quality chưa được xác minh. Không dùng sơ đồ target làm bằng chứng triển khai.
