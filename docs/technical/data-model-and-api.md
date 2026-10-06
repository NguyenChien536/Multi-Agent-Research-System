# Data Model và API — source inventory và target

**Cập nhật:** 06/10/2026. Runtime evidence gần nhất được thu 27/09/2026, ghi tại [baseline-verification.md](../project/baseline-verification.md). Bảng phân biệt source hiện trong working tree với database/API đã chạy xác minh. Không chạy migration hoặc E2E trong lượt cập nhật docs.

## 1. Model/source hiện có

| Entity / route group | Source hiện tại | Trạng thái runtime / lưu ý |
|---|---|---|
| User | UUID, username/email, full name, password hash | Model và registration route có; chưa có login/token flow hoàn chỉnh |
| ResearchTask | question, owner UUID, status, approval flag, source/iteration limits, budget/counters | POST/GET smoke-test ngày 27/09 dùng dummy user; chưa ownership enforcement |
| ResearchIteration | loop type, queries, count, verdict, timestamps | Có model/migration; workflow chưa ghi dữ liệu E2E |
| ResearchSource | task, tag, URL, metadata, source_type, image attribution fields | Model có; ingest/upload E2E chưa xác minh |
| DocumentChunk | source/task, text, pgvector embedding, vector ID | Model có; pgvector có trong DB baseline; clean DB/retrieval chưa xác minh |
| Evidence | task/source/chunk FK, quote/content, type | Model có; grounding chưa E2E |
| ResearchClaim / ClaimEvidence | Source đã có ClaimEvidence junction table; ORM bỏ UUID array cũ | Migration mới có trong working tree, chưa chứng minh apply thành công/runtime |
| Citation | report/source, nullable chunk_id FK, claim ID; deprecated chunk_reference vẫn tồn tại | Chuyển đổi schema chưa hoàn tất; cùng-task consistency cần migration/validation |
| ResearchReport | Markdown, summary/count; unique report per task | Model/route có; report versioning theo target chưa đầy đủ |
| ExportArtifact | task, type, file path/size/URL | Metadata model có; object storage/PDF flow chưa xác minh |
| AgentRun / Evaluation | Audit/evaluation entities | Model có; log privacy và evaluation pipeline chưa nghiệm thu |

**Target ERD:** [System Design — Core ERD](../architecture/system-design.md#6-core-erd--target-traceability-model). Thiết kế thêm ResearchPlan, ResearchArtifact, AnalysisRun, report versioning và durable checkpoint/run metadata. Evidence từ phân tích định lượng phải neo vào output artifact để truy về run/input/routine; citation thư mục vẫn trỏ source/chunk. Đây là target, không phải bảng đã có đủ trong DB hiện tại.

### Schema gates

1. Review migration có trong working tree; thử upgrade trên DB rỗng trước khi xem schema là đạt.
2. Enforce ClaimEvidence FK thực, Citation.chunk_id FK và quan hệ evidence/report/source/chunk cùng task; evidence của kết quả tính toán phải resolve về output artifact và AnalysisRun.
3. Thiết kế ResearchArtifact metadata: owner/task, type, storage key, checksum, upload source, provenance, retention/deletion state. File bytes không lưu trong Postgres.
4. Định nghĩa ResearchPlan/checkpoint và AnalysisRun: version, method, approval state, routine/config/input/output, status, timestamps.
5. Thêm task states WAITING_USER_DATA/PARTIAL/NEEDS_REVIEW chỉ cùng lifecycle/resume behavior.
6. Có index/filter theo task/owner và vector dimension/index trước khi benchmark.

## 2. API route inventory

Router hiện gắn dưới /api/v1. Các route phản ánh source; không đồng nghĩa mọi route đã test.

| Method / route | Source hiện tại | Evidence / gap |
|---|---|---|
| GET /api/v1/health | Health route | HTTP 200 tại baseline 27/09 |
| POST /api/v1/auth/register | Tạo user và hash password | Source có; duplicate/security/error cases chưa test |
| POST /api/v1/research | Tạo task | Smoke-test 201/PENDING đạt 27/09; dùng dummy user |
| GET /api/v1/research | List tasks | Source có; chưa smoke-test/owner filter |
| GET /api/v1/research/{task_id} | Read task | GET smoke-test đạt; chưa enforce owner |
| POST /api/v1/research/{task_id}/start | Set state/enqueue Celery | Source có; chưa dispatch E2E |
| GET /api/v1/research/{task_id}/report | Read report | Source có; chưa smoke-test/owner filter |

Login/token, approval/revise/cancel, upload/download, progress stream, WAITING_USER_DATA resume, source/evidence explorer, analysis artifacts và PDF export chưa được chứng minh là mounted/hoạt động. Stream stub không được coi là route hoạt động.

## 3. Target API groups

Khi triển khai cần chốt OpenAPI schema, auth, status/error behavior và idempotency cho các nhóm:

- Authentication/login and user session.
- Task, plan/revision/approval/cancel.
- Upload source/result artifact và ingest status.
- Resume task sau approval hoặc WAITING_USER_DATA.
- Progress event stream hoặc polling.
- Report versions, citation/evidence lineage và export.
- Analysis run summary/artifact download.

Tên route cụ thể chưa thành contract cho đến khi được khai báo trong OpenAPI và kiểm tra. API không giữ request mở cho workflow dài.

## 4. Status và security boundaries

Task target: PENDING → QUEUED/RUNNING → optional WAITING_APPROVAL/WAITING_USER_DATA → COMPLETED/PARTIAL/NEEDS_REVIEW/FAILED/CANCELLED. DB là source of truth; Redis chỉ delivery. Resume phải kiểm tra task owner/state, artifact authorization, idempotency key và checkpoint.

Uploads cần extension + MIME/magic-byte + size + checksum checks; chặn archive bombs/unsafe types; private storage; authorized downloads; retention/delete policy. Không nhận dữ liệu định danh nhạy cảm trước khi có privacy/security policy. Logs cần redaction.

## 5. Evidence cần có để nghiệm thu

- DB rỗng → migrations upgrade thành công, đúng revision, schema inspection; có kế hoạch downgrade/rollback.
- Unit/contract tests auth/ownership và chặn truy cập chéo task/file/report.
- Upload validation, object storage access, retention/delete lifecycle.
- Workflow mock-provider: idempotent job, loop/budget limits, error/retry, checkpoint/resume.
- Integration test source/chunk/evidence/claim/citation cùng-task lineage.
- Tái lập analysis artifact từ data, approved routine/version/config.
- OpenAPI contract và SSE/polling status/error coverage.
