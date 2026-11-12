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

### Contract đã triển khai 23/10 — intake thực địa (R1 / issue #39)

Các route sau thuộc `/api/v1`, có bearer auth và owner scope. Chỉ dùng khi task là EMPIRICAL_HUMAN và đang WAITING_USER_DATA; không thay thế checkpoint/versioned decisions dự kiến ở R3.

| Route | Input / output | Điều kiện và lỗi |
|---|---|---|
| POST /research/{id}/data/files | Multipart `file`; trả 201 với artifact_id, file_name, file_size_bytes, sha256_hash | CSV/TXT UTF-8 ≤5 MiB; CSV có header duy nhất, ≤30 cột/20.000 dòng. Giới hạn số file theo MAX_UPLOAD_FILES_PER_TASK. Không tự enqueue |
| POST /research/{id}/data/resume | sample_size ≥1, method_notes 10–5.000 ký tự, results_summary 10–20.000, data_provenance 10–2.000, file_artifact_id bắt buộc | 200 với QUEUED sau cùng transaction lưu submission/outbox. 422 nếu thiếu/không hợp lệ; 404 sai owner/task; 409 sai type/state hoặc lần resume thứ hai |

Artifact được nhận phải có loại USER_DATA_CSV/USER_DATA_TEXT, cùng task, có file bytes đúng kích thước và qua validation nội dung. Hiện chưa có cột trạng thái READY riêng; lưu thành công rồi kiểm lại lúc resume là điều kiện sẵn sàng. ID được serialize JSON; submission lưu checksum/trích đoạn có giới hạn và nhãn USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED. Không coi việc đính kèm file là chứng minh tính đúng khoa học; không tự dựng AnalysisRun. UI cho chọn lại file đã upload sau reload, nhập provenance và gửi một lần tiếp tục.

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


## Settings API và model — 05/11/2026

### Thông tin cá nhân

`GET /api/v1/auth/me` đọc hồ sơ; `PATCH /api/v1/auth/me` cập nhật tài khoản đang đăng nhập. Các trường cho phép: `full_name` (tối đa 100 ký tự, có thể xóa), `username` (3–50 ký tự), `email` (email hợp lệ, tối đa 255 ký tự). Chỉ gửi trường cần sửa; không nhận user ID hoặc trường nội bộ. Đổi email cần `current_password` đúng; lần đăng nhập tiếp theo dùng email mới. Trùng email/username trả 409, sai/thiếu mật khẩu đổi email trả 403, dữ liệu sai trả 422, chưa đăng nhập trả 401. Mật khẩu không được trả trong response hoặc lỗi validation. Không đổi password, quyền sở hữu bài hoặc cấu hình model khi sửa hồ sơ. Các trường đã có trong bảng users nên không cần migration.

Giao diện: **Settings → Thông tin cá nhân** trên trang `/settings` và hộp thoại Settings. Sau khi lưu, thông tin ở thanh bên được cập nhật ngay. Email mới chưa được xác minh bằng email; đây là luồng tài khoản local, chưa có hệ thống gửi thư xác minh.

Hồ sơ mặc định chỉ xem; bấm **Chỉnh sửa** để mở form, **Lưu thay đổi** mới gửi PATCH, **Hủy** bỏ bản nháp. **Xóa tài khoản** mở xác nhận riêng: nhập mật khẩu hiện tại và đúng chữ `DELETE`. `DELETE /api/v1/auth/me` nhận `current_password`, `confirmation`, trả 202. Migration `f297c20d0003` thêm `users.deleted_at` làm ý định xóa bền vững. Ngay sau xác nhận, đăng nhập/token cũ và provider calls mới bị từ chối, key mặc định bị gỡ. Dispatcher đánh dấu từng bài để tái sử dụng outbox xóa file; worker chờ lease đang hoạt động, xóa file và checkpoint đúng thread rồi xóa dữ liệu task. Chỉ xóa bản ghi tài khoản khi hết task. Lỗi cleanup giữ ý định/outbox để retry qua lần khởi động sau, không cascade mất thông tin dọn file. Khóa tài khoản không thể hủy qua giao diện. Các backup ngoại tuyến có sẵn không tự bị xóa bởi endpoint này; quy trình backup/khôi phục được quản lý riêng.

`users.model_connection` lưu JSONB gồm profile công khai và ciphertext owner-bound; API không trả key/ciphertext. Bài mới mặc định giải mã cấu hình chủ sở hữu rồi mã hóa lại theo task ID, giữ snapshot riêng. Đổi cấu hình mặc định không đổi các bài cũ. Các endpoint bên dưới yêu cầu đăng nhập và quyền sở hữu:

| Endpoint | Ý nghĩa |
|---|---|
| GET/PUT/DELETE `/api/v1/settings/model-connection` | Đọc profile, lưu/cập nhật hoặc xóa mặc định; key bỏ trống giữ key cũ khi cùng dịch vụ |
| PUT `/api/v1/settings/research/{id}/model-connection` | Đổi kết nối riêng khi bài không RUNNING/QUEUED |
| POST `/api/v1/settings/research/{id}/use-default` | Áp dụng snapshot mặc định cho bài đã dừng/chờ |
| POST `/api/v1/settings/research/{id}/save-as-default` | Lưu kết nối bài làm mặc định mà không trả key về browser |

`output_token_limit` và `reasoning_effort` là cấu hình model; reasoning hiện áp dụng qua OpenRouter. `fallback_models` là danh sách tùy chọn tối đa ba ID OpenRouter `:free`, giữ nguyên thứ tự đã chọn; API chỉ nhận danh sách này với kết nối OpenRouter có đơn giá bằng 0, và request luôn đặt trần giá bằng 0. Danh sách nằm trong profile mã hóa của mỗi bài, không cần migration. Giới hạn ngân sách task vẫn độc lập và không reset khi đổi model. Xóa mặc định không thu hồi snapshot của bài cũ; từng bài có thao tác thu hồi key riêng. Catalog công khai chỉ có địa chỉ/model metadata, không có tài khoản hoặc key.

Khi provider trả 429, worker lưu checkpoint hiện tại và thời điểm thử lại vào transactional outbox, nhả slot và đặt task ở `QUEUED`; không giữ request/worker ngủ trong lúc chờ. Hệ thống tôn trọng `Retry-After`/`X-RateLimit-Reset`, nếu thiếu thì backoff; việc thử lại không có giới hạn số lần tự dừng nhưng người dùng có thể hủy. Hạn mức miễn phí chung được chờ đến thời điểm reset thay vì chuyển qua model khác để né quota. Các lỗi xác thực, dữ liệu request không hợp lệ, hết ngân sách bài và hạn mức chi tiêu không được tự retry. Đây là cơ chế phục hồi tác vụ, không phải bảo đảm nhà cung cấp sẽ sớm cấp quota hoặc model dự phòng sẽ viết tương đương.
