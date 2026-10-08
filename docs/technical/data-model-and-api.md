# Data Model and API — baseline và hợp đồng mục tiêu

**Rà soát source:** 08/10/2026 tại `ebb525a`. Các bảng/route ghi “target” chưa được xem là đã migration/mount. [System Design](../architecture/system-design.md) chứa ERD chuẩn; [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md) chốt cơ chế run/versioning.

## 1. Hiện trạng đọc code

| Nhóm | Có trong source | Khoảng cách |
|---|---|---|
| Identity | User, register và password/JWT helpers | Login/current-user/ownership trên research routes chưa đủ; còn dummy_user_id |
| Research | Task, ResearchIteration; create/list/get/start/report | Start thiếu transition guard/idempotency; chưa có ResearchRun riêng |
| Provenance | Source, Chunk, Evidence, Claim, ClaimEvidence, Citation | Analyst chưa persist đầy đủ lineage; validator còn placeholder |
| Output | ResearchReport, ExportArtifact | Một report/task; chưa hỗ trợ report versions |
| Execution | AgentRun/evaluation metadata | Chưa có đầy đủ artifact/run/checkpoint/event contracts mục tiêu |

Migration ClaimEvidence/Citation.chunk_id đã được commit trong `ebb525a`; không gọi là “chưa commit”. Chưa có evidence áp dụng migration này trên DB sạch/DB hiện hành. Runtime gần nhất ghi 27/09.

## 2. Mô hình mục tiêu

| Entity | Mục đích và khóa/ràng buộc chính |
|---|---|
| User | Owner workspace; mọi query/download kiểm quyền |
| ResearchTask | Workspace **một bài báo**; owner_id, article_type, snapshot trạng thái/việc cần làm; user có nhiều task độc lập |
| ResearchRun | Một execution/revision; task_id, base_report_id?, plan_id nullable trước planning, plan_version, status, stage, lease/version, budget/counters; một active run/task |
| ResearchPlan | Version immutable; task_id, version, article_type REVIEW/EMPIRICAL_COMPUTATIONAL/EMPIRICAL_HUMAN, study_path, method/config; unique(task_id, version) |
| Source / DocumentChunk | Nguồn web/PDF có hash/locator; chunk thuộc source và task; corpus gắn embedding profile |
| ResearchClaim | Nhận định, mức độ chắc chắn và phạm vi; thuộc task/run tạo ra |
| Evidence / ClaimEvidence | Evidence neo đúng một chunk hoặc artifact; claim–evidence nhiều-nhiều, có stance/support/contradict |
| ResearchArtifact | File upload hoặc output; kind (input/protocol/form/draft/result/chart/export), owner/task, checksum, storage_key, validation_status; producer_analysis_run_id nullable |
| AnalysisRun | run_id, input_artifact_id, routine/code/image version, config/seed, status, conclusion riêng với execution status, metrics/manifest refs; input/output không được đánh tráo |
| ExperimentJournalEntry | Append-only theo task/AnalysisRun; sequence, kind, attempt_id?, plan_version, actor, timestamp, schema-versioned payload, artifact IDs/checksums, idempotency key; plan, mọi attempt, quan sát, diễn giải và rerun đều giữ |
| ResearchReport / ReportClaim | Report version và các claim thực sự có trong version đó; task_id/run_id, article_type, validation_status, completeness_status, unique(task_id, version). Protocol/draft chưa có Results không là report COMPLETED |
| Citation | Tham chiếu thư mục từ report/claim tới source và optional chunk; không dùng làm đường duy nhất cho kết quả phân tích |
| AgentRun | Role/model/prompt version, timestamps, status, usage/cost và references; không chứa secrets/raw reasoning |
| Q&A operation metadata | operation_id, task_id, report_version, idempotency key, cap/usage, answer references; reuse operation/usage store, không cần graph run mới để hỏi bài |
| TaskEvent | Event ID theo task, run_id, kind, timestamp, public payload; DB là nguồn replay |
| DispatchOutbox | Operation ID, run/checkpoint/version, payload, dispatch state/retry; ghi cùng transaction với operation |
| LangGraph checkpoints | Namespace riêng trong PostgreSQL; thread/checkpoint gắn run và plan version |

**Lineage:** report → ReportClaim → claim → ClaimEvidence → evidence → chunk → source; hoặc evidence → artifact → AnalysisRun → input artifact. Citation là thư mục tài liệu, còn bảng/biểu đồ thực nghiệm dùng evidence/artifact references. Ảnh minh họa không được dùng làm evidence thực nghiệm.

`TaskEvent`/`AgentRun` phục vụ vận hành; `ExperimentJournalEntry` là hồ sơ khoa học, không lấy raw log làm Results. Unique `(analysis_run_id, sequence)` và idempotency key chống ghi lặp; correction thêm entry mới. `NO_IMPROVEMENT` là kết luận của run hợp lệ, `TECHNICAL_FAILURE` là lỗi, không được gộp. Manifest được đóng băng trước chạy; một rerun mới cùng manifest ghi kết quả đối chiếu riêng trước khi gắn nhãn “ATI đã tái lập”. Field và trạng thái chi tiết: [Experiment Journal](experiment-journal-and-reproducibility.md).

Database constraints kiểm cùng task/owner qua composite FK/unique phù hợp; không chỉ dựa UUID tồn tại. Evidence có CHECK đúng một anchor, source phải khớp chunk; ReportClaim/Citation không trỏ claim ngoài report/task. Artifact upload không có analysis producer; artifact kết quả tính toán do ATI sinh phải trỏ AnalysisRun thành công và checksum/manifest đã validate. Protocol/export do workflow sinh không bắt buộc có AnalysisRun, nhưng giữ run/report version tạo ra chúng. User-supplied results có nhãn nguồn, file hash, phương pháp/đơn vị/mẫu và provenance người cung cấp; không tự tạo AnalysisRun giả. Các invariant vượt khả năng FK được kiểm transaction/validator, không khẳng định FK chứng minh ý nghĩa claim.

## 3. Vòng đời và event

Lifecycle target: PENDING → QUEUED → RUNNING → WAITING_APPROVAL / WAITING_USER_DATA → QUEUED; terminal COMPLETED / PARTIAL / NEEDS_REVIEW / FAILED / CANCELLED. Stage (planning/searching/analyzing/writing/reviewing/exporting) là trường riêng. Chuyển trạng thái bằng CAS/version, không overwrite vô điều kiện.

| Thao tác | Điều kiện | Kết quả |
|---|---|---|
| Start | Task PENDING, owner hợp lệ, chưa active run **trên task này** | Run mới QUEUED + outbox trong transaction; task khác độc lập |
| Claim job | Operation/version hợp lệ, lease khả dụng | RUNNING; duplicate không chạy side effect lần hai |
| Interrupt | Đang RUNNING, checkpoint ghi thành công | WAITING_APPROVAL hoặc WAITING_USER_DATA; worker trả job/lease |
| Approve/resume | Đang WAITING_*, đúng owner/plan/checkpoint, data READY khi cần | Giữ run_id, QUEUED + resume outbox; không reset counters/budget |
| Revise plan đang chờ | Đúng active run/plan version, trong policy | Plan version mới; giữ run và budget, invalidates results của config cũ |
| Finalize | Gate của article_type đạt hoặc có lý do dừng rõ | COMPLETED chỉ với bài báo đủ phần/Results cần thiết; terminal khác giữ đúng nhãn, report version không ghi đè |
| Revise bài sau terminal | Có base_report_version, không active run | Run mới với budget mới trong project cap; giữ report cũ |
| Cancel/delete | Owner hợp lệ; operation idempotent | Cancel tại safe boundary; delete tombstone ngay và cleanup theo SRS |

QUEUED, RUNNING và WAITING_* đều tính là active run **trong cùng task**. Chờ người dùng không giữ worker lease hoặc suất RUNNING, nhưng vẫn chặn start/research revision khác **trên task đó**; trả 409 cùng hướng dẫn revise plan/resume hoặc cancel. User tạo/chạy task khác trong lúc này. Dispatcher/worker claim tối đa 2 RUNNING/user theo mặc định; QUEUED/outbox không mất khi hết suất, dispatch công bằng khi slot trống. PENDING là trạng thái task chưa có run, không phải một worker đang chờ. Q&A có thể đọc report version đã tồn tại, với operation/cap riêng và ownership; không sửa run đang chạy.

DB transaction ghi operation + outbox; API background dispatcher publish Celery job. Quota 2 RUNNING/user phải được cấp bằng **DB transaction khóa hàng user/quota hoặc cơ chế khóa tương đương**, đếm lease chưa hết hạn và cập nhật claim atomically; không dựa vào `COUNT` rời rạc hoặc số worker process. Dispatcher chỉ phát job đủ suất, job khác ở QUEUED/outbox có retry/wakeup khi suất trống; worker kiểm lại quyền claim trước side effect để chống delivery lặp. Lease hết hạn được reconciliation trước khi cấp lại, không cho hai run cùng tiếp tục ghi. Event ghi DB rồi mới Pub/Sub; SSE reconnect lấy lại event hoặc snapshot. Không coi Celery ack là chứng minh task chỉ chạy một lần.

## 4. Route inventory và target API

Tên tài nguyên dưới đây là **contract thiết kế**, implementation phải thống nhất schemas trước khi mở rộng UI. Research routes hiện nằm dưới `/api/v1/research`; target giữ prefix này để giảm thay đổi.

| Operation | Hiện tại | Target |
|---|---|---|
| Register | Có route source | Validate identity và duplicate; password hash |
| Login/current user | Chưa hoàn chỉnh | POST /auth/login; GET /auth/me; token + owner filter |
| Tạo task | POST /research, 201 | 201 Created, workspace PENDING |
| List/get | GET /research và /research/{id} | Filter owner; list nhiều task với status/stage/next_action/updated_at/latest_report_version; resource khác owner trả 404 |
| Start | POST /research/{id}/start; trả 200 PLANNING | 202 Accepted + run_id sau transaction/outbox; Idempotency-Key |
| Tiến độ | UI polling task | GET task snapshot; GET /research/{id}/events có SSE replay và auth |
| Upload | Chưa triển khai đủ | POST /research/{id}/artifacts → validate → READY hoặc REJECTED; không resume file chưa READY |
| Duyệt/sửa/cancel plan | Chưa đủ | POST /research/{id}/decisions với plan_version/checkpoint_id và idempotency key |
| Resume với dữ liệu | Chưa đủ | POST /research/{id}/resume với checkpoint/plan_version và artifact_ids READY; 202, QUEUED bền vững nếu hết suất RUNNING |
| Report/Q&A | GET /research/{id}/report; chưa version/Q&A | GET report version; POST /research/{id}/questions với report_version/idempotency key; operation/cap riêng, không research ngầm |
| Revision | Chưa có | POST /research/{id}/revisions, base_report_version + yêu cầu; 202; version mới |
| Cancel | Chưa có hợp đồng đầy đủ | POST /research/{id}/cancel; idempotent; dừng tại safe boundary |
| Export/download | Chưa đủ | Export Markdown/package; GET artifact qua API kiểm quyền; file private |
| Nhật ký thí nghiệm | Chưa có | GET /research/{id}/analysis-runs/{analysis_run_id}/journal theo owner; timeline phân trang và export có manifest/attempt/rerun, không lộ raw secrets |
| Delete | Chưa đủ | DELETE task; tombstone trước, purge theo policy, không resume sau delete |

Các route rút gọn trong bảng đều ở `/api/v1`. Mã lỗi: 401 thiếu token, 404 không có quyền/tài nguyên, 409 stale version/state conflict, 413 vượt size, 422 sai schema/routine, 429 vượt quota. Operation lặp cùng key+payload trả cùng kết quả; cùng key khác payload trả 409. Upload nội dung lớn có thể 202 processing; UI chờ READY trước resume.

## 5. Files và dữ liệu phân tích

Private ArtifactStore dùng local volume cho bản nộp, có interface thay object storage sau này. DB lưu metadata/checksum, không file bytes. PDF chỉ text extraction trong giới hạn SRS; không hứa OCR. CSV numeric theo schema routine, không dùng RAG để tính thống kê.

Runner nhận immutable manifest với input hash/config/seed/routine version; trả metrics/charts/log/manifest có kiểm tra schema và paths. Không chấp nhận đường dẫn ngoài staging directory. Writer chỉ diễn giải ATI-executed Results từ analysis run thành công; kết quả người dùng cung cấp phải qua kiểm provenance và ghi nhãn riêng, nếu thiếu thông tin thiết yếu thì giữ WAITING_USER_DATA/NEEDS_REVIEW. Thay input/method khi run còn active tạo plan version/analysis execution mới, giữ counters/budget và vô hiệu hóa results cũ; revision sau terminal mới tạo ResearchRun mới.

Delete trả thành công sau khi tombstone bền vững, không có nghĩa file bytes đã purge. Mọi writer/ingestion/runner completion kiểm tombstone trước publish/persist; output tạm đến muộn được cleanup. Cleanup theo [NFR-07](../requirements/SRS.md#7-chất-lượng-và-dữ-liệu), có retry và bằng chứng deadline; không để file/index/checkpoint còn truy cập được qua URL cũ.

## 6. Thứ tự migration

1. Auth ownership + ResearchRun/lifecycle + outbox/events.
2. Provenance constraints, embedding profile, plan schema/version cơ bản, report/version/ReportClaim (P2).
3. Upload/artifact/tombstone hooks (P3), checkpoint và approval decision (P4).
4. AnalysisRun, ExperimentJournalEntry append-only, routine manifest, rerun records và provenance kết quả (P5).

Backfill data cũ phải đánh dấu thiếu lineage; không tạo evidence giả để migration pass. Giữ DB demo riêng khi thử upgrade/downgrade. Chi tiết nhiệm vụ và gates ở [Implementation Plan](../project/implementation-plan.md).
