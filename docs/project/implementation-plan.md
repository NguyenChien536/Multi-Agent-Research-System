# Kế hoạch triển khai đã chốt — ATI

**Chốt:** 08/10/2026 · **Hạn:** 10/11/2026 · **Baseline source:** `ebb525a`.<br>
Phạm vi theo [SRS v4.0](../requirements/SRS.md); lý do và findings ở [Product Assessment](product-assessment.md). Đây là backlog đề xuất, **chưa phải các GitHub issues đã tạo**.

## 1. Quy tắc thực hiện

- Giả định để lập lịch (chưa đo năng lực): Chiến có 3–4 giờ tập trung/ngày, khoảng 90–115 giờ còn lại. P0–P7 ước lượng 83–108 giờ; buffer nhỏ, không thêm feature ngoài scope.
- Mỗi gói là một lát cắt có thể kiểm tra; cần chia nhỏ PR nếu vượt khoảng 2 ngày làm việc. Giữ một feature branch/PR đang triển khai cho Chiến; ba thành viên nghiên cứu/QA song song.
- Cùng thư mục làm việc; không cần tạo thêm checkout. Ví dụ branch `codex/p1-auth-task-lifecycle`; base là nhánh tích hợp đã chứa prerequisite và được chọn rõ trước khi bắt đầu. Không mặc định có `develop` hoặc merge trực tiếp `main`.
- Chu trình: đọc issue/contract → plan ngắn → code → checks phù hợp → review diff → sửa findings → lưu evidence → merge qua PR. Codex/Antigravity đọc cùng SRS, ADR và file này; tool/model có thể thay mà contract không đổi.
- Done cần source + checks + runtime evidence phù hợp; tài liệu ghi planned/implemented/verified tách biệt. Stub-provider test không thay run provider thật cuối cùng.
- Mỗi issue/PR ghi FR/NFR liên quan và gate G0–G7 theo [SRS §8–9](../requirements/SRS.md#8-acceptance-gates). Gói P0–P7 là thứ tự triển khai, khác với mức ưu tiên lỗi P0/P1 trong Product Assessment.

## 2. Dependency và lịch

`P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7`. Monitoring tối thiểu bắt đầu ở P1, citation/loops làm ở P2; không chờ tới cuối mới kiểm chất lượng.

| Gói | Mốc mục tiêu | Giờ Chiến | Đầu ra | Gate |
|---|---|---:|---|---|
| P0 · baseline tái lập | 08–10/10 | 4–6 | Runtime/dependency thống nhất, DB sạch, test isolation | G0: dựng lại được, tests không gọi dịch vụ thật |
| P1 · auth và lifecycle | 11–14/10 | 10–13 | Owner, ResearchRun, start/cancel/idempotency, outbox, events | G1: không truy cập chéo/dispatch lặp |
| P2 · research E2E có evidence | 15–19/10 | 15–18 | Web → persisted evidence → draft/critic → citations, budget | G2: một review chạy thật trong cap |
| P3 · PDF và workspace UI | 20–23/10 | 10–13 | Upload/ingest, evidence explorer, stage/event timeline | G3: web + PDF chung task, UI thấy lỗi/partial |
| P4 · plan/protocol/resume | 24–26/10 | 8–11 | Assisted/automatic, PostgreSQL checkpoint, durable waits | G4: restart/resume đúng, protocol qua review |
| P5 · experiment thật | 27–30/10 | 14–18 | Routine runner CSV, metrics/charts, empirical manuscript, reproducibility | G5: cùng input/config tái lập được |
| P6 · Q&A/revision và hoàn thiện | 31/10–02/11 | 8–10 | Hỏi đáp có nguồn, report versions, authorized export | G6: sửa giữ bản cũ, không dùng result lỗi thời |
| P7 · evaluation và bản nộp | 03–07/11 | 14–19 | Baseline/ablation, QA, sửa blockers, evaluation report | G7: evidence đủ, failures/limits công khai |
| Buffer / freeze | 08–10/11 | Ngoài ước lượng trên | Dry run, backup demo, đồng bộ báo cáo/AI disclosure | Không thêm feature |

## 3. Nội dung từng gói

### P0 — Baseline và môi trường

- Chốt Python 3.11 cho backend/local dev để khớp Docker hiện có; root scaffold 3.14 phải đồng bộ hoặc ghi rõ không phải entrypoint backend.
- Khóa bộ backend dependencies tương thích (LangGraph/checkpointer/provider integrations/SQLAlchemy); không nâng hàng loạt chỉ để dùng API mới trên docs.
- DB test riêng: empty DB → Alembic head `a1b2c3d4e5f6`; kiểm migration/data backfill. Không xóa volume dev để giả lập DB sạch.
- Tách API test hiện có khỏi broker/real providers; dùng fake dispatch/provider trong tests. Ghi hiện trạng frontend build và các lỗi thực tế.
- Artifact nghiệm thu: command, exit status, revision và log đã redacted; thêm entry có ngày vào baseline verification.

### P1 — Auth, run và dispatch reliability

- Login/token hoặc session, dependency current_user, owner-scoped query cho mọi route; registration chỉ là bước tạo tài khoản.
- ResearchRun, status/stage và transition table; compare-and-set start, một active run/task, idempotency key. Task POST vẫn tạo tài nguyên 201; start/resume được nhận vào queue trả 202.
- Transactional outbox cùng task/run; dispatcher nền trong API lifespan claim/retry, worker claim/lease; không dựa riêng Celery task ID/acks_late. Cancellation kiểm trước mỗi stage/tool, stale worker không ghi terminal đè run mới.
- TaskEvent/AgentRun từ đầu; JSON logs, task/run/step ID; UI polling snapshot trước, SSE khi contract ổn.
- Gate: user A/B isolation; double start; broker unavailable; worker redelivery; cancel; no silent queue loss.

### P2 — Một luồng research thực sự có căn cứ

- Provider gateway + budget reserve/reconcile cho search/LLM/embedding/retries/fallbacks. Model/price/profile cấu hình, không tự đổi provider ngoài data policy.
- Safe fetch có connection-level address policy và size/type/time limits; retry hữu hạn, không nuốt lỗi thành “không có nguồn” rồi báo thành công.
- Immutable delta_sources, canonical URL/hash dedup; pin embedding profile, lưu chunk/source/task IDs và locators.
- Analyst structured output chọn chunk IDs trong retrieved set, quote xác minh với text; persist Evidence/Claim/ClaimEvidence. Writer dùng evidence bundle và references xác định; không tự bịa citation.
- Tạo nền ResearchReport version/ReportClaim từ P2 cho REVIEW v1; P6 mới mở thao tác revision/Q&A. Lưu plan schema/version cơ bản từ P2, P4 bổ sung approval/checkpoint; tránh tạo report hoặc plan tạm không thể migration sang contract đã chốt.
- Critic đọc toàn bài theo section + evidence/method/results. Typed verdict PASS/REVISE/NEED_EVIDENCE/NEED_METHOD_REVIEW; targeted queries; 3 research rounds, 2 revisions; no-delta stop; deterministic citation gate.
- Gate: no-source/contradiction/budget/invalid-citation tests; report không hợp lệ không COMPLETED; một provider-backed run nhỏ trong cap sau khi guard hoạt động.

### P3 — Nguồn riêng và giao diện quan sát

- ArtifactStore private local volume; upload status, metadata/checksum, PDF text parser có limits. Không OCR; lỗi hướng dẫn người dùng rõ.
- File/ingestion job gắn owner/task và tombstone check từ đầu; thống kê mọi storage key/index/checkpoint cần cleanup để P6 triển khai xóa đầy đủ.
- Ingestion độc lập/idempotent; source READY mới được retrieve; embedding nhất quán web/PDF. Tắt cache private nếu chưa enforce scope/retention.
- UI login/create/detail; role/stage/status/round/budget, timeline, evidence/source passages, report và warnings. Owner-only API fetch, sanitize Markdown.
- Gate: PDF hợp lệ/quá lớn/malformed/không text; foreign artifact denied; reconnect polling đúng trạng thái, không fake phần trăm tiến độ.

### P4 — Plan, protocol, pause/resume

- Plan versions, policy-assisted/automatic và audit decision. Methodologist chỉ chạy khi protocol/experiment cần; review path bỏ qua roles đó.
- PostgreSQL checkpointer/thread ID, interrupt trả về worker như WAITING, không coi thiếu report là exception. Side effects trước interrupt phải idempotent.
- Human-led protocol qua Writer/Critic/Validator; artifact có trước khi chờ, task không COMPLETED trong lúc WAITING_USER_DATA.
- Resume chỉ sau owner/state/checkpoint/plan version đúng và data READY; unsupported input trả lỗi hoặc tiếp tục chờ. Không tự dựng “user supplied summary” khi chưa có file kết quả.
- Gate: restart worker/API; duplicate approval/upload/resume; stale plan decision; wait không giữ worker và không đếm active-time.

### P5 — Experiment hẹp chạy thật

- Routine `tabular_regression_v1`: numeric CSV, profile dữ liệu, mean baseline vs Ridge(alpha=1), split/seed định trước; preprocessing fit train-only.
- Experiment spec ghi câu hỏi, giả thuyết khi có, dataset, columns, metric, split/seed, limits. Không thay hypothesis/metric sau khi thấy test để săn kết quả tốt.
- Trusted host launcher chạy Docker job container riêng theo manifest; API/worker không có Docker socket. Routine/code/image pin, network off, non-root, caps/resource/output limits.
- Lưu AnalysisRun/input/output hash/exit code/log redacted; metrics JSON/CSV, plots PNG, manifest, config, routine source/launcher và README tái lập. Validate schema/finite numbers/artifact paths trước Writer.
- Data Analyst diễn giải actual output; Writer viết Methods/Results có provenance, phân biệt exploratory/predictive và không tuyên bố causal.
- Gate: empty/invalid CSV, target leakage, timeout/OOM, forged artifact, repeatability. Routine thất bại không tạo Results. Bộ data và expected checks do Vũ bàn giao trước 16/10.

### P6 — Hỏi đáp, sửa và xuất

- Q&A đọc report version/evidence, không kích hoạt research lại ngầm; câu hỏi ngoài nguồn phải nói thiếu căn cứ.
- Mỗi Q&A có operation ID/cap riêng trong quota task, dùng provider gateway; không reset budget research run đã đóng. Kiểm câu hỏi lặp/rate limit, thiếu budget và không đọc report của owner khác.
- Revision dùng base_report_version và unique request; lưu version mới; đổi data/method tạo plan/run mới, không tái sử dụng kết quả của input cũ.
- Authenticated event stream/reconnect theo DB event IDs nếu triển khai SSE; polling vẫn là nghiệm thu tối thiểu.
- Export Markdown và experiment package qua API; protocol/report đều kiểm lineage trước phát hành. PDF polished/image enrichment để sau.
- Xóa task: tombstone chặn read/resume/late writes ngay, cancel tại safe boundary; cleanup có retry trong 24 giờ, backup retention tối đa 7 ngày theo SRS. Gate gồm xóa task đang chạy/chờ, duplicate cleanup và file không bị tạo lại bởi worker cũ.

### P7 — Đánh giá và bàn giao

- Chạy [Evaluation Plan](evaluation-plan.md), chỉ công bố số thực đo. Chạy provider tốn phí phải nằm trong cap riêng đã cấu hình cho đợt evaluation.
- Vũ/My chấm nội dung theo blind labels; Hiếu chạy kịch bản và ghi lỗi; Chiến sửa P0/P1 blockers và xác nhận runtime.
- Cập nhật midterm/final progress, limitations, acceptance matrix; AI disclosure theo đóng góp thực tế, không điền tỷ lệ tùy ý.

## 4. Điều kiện dừng mở scope

Nếu G2 chưa đạt 19/10, cắt PDF đẹp/ảnh/SSE nâng cao và UI trang trí. Nếu G4/G5 trễ hơn 2 ngày, thu nhỏ dataset/template và dành thời gian cho lỗi nền; báo rõ các cam kết chưa đạt. Không bỏ ownership, citation lineage, budget, kết quả thật hoặc evaluation để thay bằng demo đẹp.

## 5. Bước bắt đầu ngay

Thực hiện **P0 trước**: baseline tái lập + DB sạch/test isolation, sau đó P1. Không tạo agent mới trước khi G1/G2 đạt. Chiến ghi một command/evidence log; Vũ chuẩn bị query/dataset, Hiếu scenarios, My nguồn/template theo [Team Task Guide](team-task-guide.md).

## 6. Bàn giao giữa các gói

Một gói chỉ được đánh dấu Verified khi có: FR/NFR + gate, commit/revision, môi trường/config không chứa secrets, lệnh hoặc bước thao tác, expected/actual, output/log đã che dữ liệu và người xác nhận. Phân biệt fake-provider checks với run provider thật.

Roadmap ghi Planned / In progress / Implemented / Verified / Blocked theo evidence thực tế. Khi phát hiện lỗi làm gate đã đạt không còn đúng, mở lại gate và ghi regression; không chỉ sửa ngày trên timeline. Giá trị nghiệm thu của từng gate nằm tại SRS, cách đo nằm tại Evaluation Plan; không đặt điều kiện khác trong issue/PR.
