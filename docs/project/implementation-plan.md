# Kế hoạch triển khai đến production — Synthia

**Chốt kế hoạch:** 23/10/2026 · **Cập nhật tiến độ:** 24/10/2026, develop@b2e39b7 · **Mốc nộp/demo:** 10/11/2026.

Đây là nguồn duy nhất về **việc cần làm, thứ tự và điều kiện phát hành**. [Roadmap](roadmap-and-progress.md) ghi việc đã làm; [biên bản](baseline-verification.md) ghi bằng chứng. P0–P7/G0–G7 giữ ý nghĩa trong [SRS](../requirements/SRS.md); P8–P10 bổ sung đường đến production. Lịch này thay lịch 12/10 đã lỗi thời.

## 1. Định hướng đã chốt

**Giữ hướng Multi-Agent Research Orchestrator.** Hệ thống nhận câu hỏi/nguồn riêng, lập kế hoạch, tìm bằng chứng, chọn phương pháp, phân tích khi phù hợp, phản biện và tạo **bản thảo bài báo hoàn chỉnh theo loại nghiên cứu**. Người nghiên cứu chịu trách nhiệm kiểm tra trước khi sử dụng/công bố; bản thảo đủ cấu trúc không đồng nghĩa đã được bình duyệt.

| Luồng | Người dùng làm gì? | Đầu ra | Điều kiện hoàn thành |
|---|---|---|---|
| REVIEW | Đưa câu hỏi, có thể thêm PDF, duyệt kế hoạch nếu muốn | Bản thảo tổng quan, nguồn/bằng chứng, gợi ý research gap và giới hạn | Claim truy được nguồn, phản biện toàn bài; không tự gọi là systematic review/PRISMA nếu chưa đủ quy trình |
| EMPIRICAL_COMPUTATIONAL | Thêm CSV phù hợp routine, xác nhận phương pháp | Methods/Results từ số liệu thật, bảng/biểu đồ, journal và gói chạy lại | Routine chạy trong runner riêng; không dựng Results khi chạy thất bại |
| EMPIRICAL_HUMAN | Nhận protocol, thực hiện bên ngoài, tải kết quả lên | Protocol lúc chờ; bài thực nghiệm khi đủ dữ liệu và provenance | Không biến mô tả do người dùng nhập thành kết quả đã được hệ thống xác minh |
| Nhiều bài và chỉnh sửa | Mở A/B/C/D…, chuyển bài, hỏi và sửa | Workspace và lịch sử riêng cho từng bài | WAITING không giữ worker; tối đa 2 RUNNING/user; quota lưu trữ/hàng đợi riêng |

REVIEW dùng **Supervisor, Researcher, Evidence Analyst, Writer, Critic**. Methodologist/Data Analyst chỉ tham gia khi cần. Parser, validator, exporter và runner là module code. Giá trị đa tác tử cần đo qua phân công, evidence dùng chung và vòng phản biện có giới hạn; không lấy số agent làm thước đo chất lượng.

**Không mở scope trước khi khép gate hiện tại:** không code tùy ý do AI sinh, GPU training, OCR, nhóm cộng tác hoặc marketplace. Ảnh minh họa/PDF trình bày đẹp để sau; ảnh cần attribution và cho người dùng bỏ. Không thay thực nghiệm thật bằng mock để báo hoàn thành.

## 2. Kiến trúc và công nghệ

Giữ **modular monolith**: backend chia module nghiệp vụ; API và worker là các tiến trình triển khai riêng. Chưa tách mỗi agent thành microservice. [System Design](../architecture/system-design.md) là thiết kế mục tiêu, không phải danh sách chức năng đã nghiệm thu.

| Thành phần / pattern | Quyết định | Điều kiện cần khép |
|---|---|---|
| Next.js + FastAPI | UI gọi API có xác thực; polling là nền, SSE chỉ thêm khi có replay/reconnect | Browser E2E login/create/upload/wait/resume/report; session hết hạn rõ ràng |
| LangGraph + state machine | Roles có input/output schema; Postgres checkpointer theo workflow run, interrupt cho approval/data wait | Resume đúng node/version; còn cần fault test worker process restart và kiểm tra side effect idempotent khi redelivery |
| PostgreSQL + pgvector | Nguồn chuẩn cho owner, run, versions, evidence, journal và outbox | Migration dữ liệu cũ, constraints/index; pin embedding profile, không trộn vector khác model |
| Transactional outbox + Celery/Redis | Ghi yêu cầu chạy cùng transaction DB, retry hữu hạn, claim có lease | ACK/redelivery cấu hình rõ; delivery có thể lặp nên ghi output phải idempotent; thử crash thật |
| Provider gateway | Một đường gọi LLM/search/embedding có quota, timeout, retry, usage ledger | Reserve trước từng call/retry/fallback; server áp cap, không chỉ cộng tiền sau call |
| Ports/adapters | Bao provider, ArtifactStore và runner bằng interface | Fake dùng cho test; không trả fake output khi provider thật hỏng |
| Isolated runner | Routine ID/config/artifact IDs được cho phép; job riêng | API/worker không có Docker socket; không nhận shell/code LLM; tính toán không chặn Celery workflow |
| Private artifact storage | Local volume dev; S3-compatible private bucket khi triển khai | Owner-only download/URL ký ngắn hạn, checksum, cleanup, backup cùng metadata |
| Observability | JSON log theo request/task/run/step; metrics/cảnh báo độc lập UI | Không log secrets/nội dung riêng; queue age, lease, errors, cost, runner, cleanup |

Restricted container là lựa chọn cho **routine tin cậy**. Nếu mở code tùy ý sau này phải có ADR về sandbox, network policy, đánh giá bảo mật/chi phí; không coi Docker đơn thuần là bảo đảm an toàn cho mã thù địch.

Nguồn kỹ thuật: [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [Celery acknowledgement và idempotency](https://docs.celeryq.dev/en/stable/userguide/tasks.html). Dùng thư viện chưa đủ; phải kiểm hành vi thực tế.

## 3. Backlog audit phải xử lý trước

Baseline audit ngày 22/10 có **74 backend tests, FE lint/build đạt**. Sau R1–R3, suite hiện có **109 backend tests**; G1–G7 vẫn chưa đạt đầy đủ và hệ thống chưa production-ready. Chi tiết baseline tại [biên bản audit](baseline-verification.md#kiem-tra-2026-10-22). R1–R8 là mã đầu việc tại đây, không phải số GitHub issue.

| Thứ tự | Vấn đề thực tế | Cách sửa đã chọn | Nghiệm thu |
|---|---|---|---|
| R1 | FE bỏ token ở /auth/me; data/resume có UUID lỗi JSON, thiếu file/provenance vẫn QUEUED | Chỉ bỏ token với login/register; serialize JSON đúng; artifact phải READY, đúng owner/task/type; intake có provenance | Token, UUID, file thiếu/sai owner, duplicate resume; G1/G4 |
| R2 | Budget chưa chặn trước call; cancel chưa chặn graph gọi tool tiếp | Gateway + ledger reserve/reconcile; kiểm cancel/lease trước stage/call/side effect | Hết cap không có call tiếp; tính retry/fallback/embedding; không output muộn. Không hứa thu hồi call provider đã nhận; G1/G2 |
| R3 | Resume dựng lại graph từ đầu; thiếu checkpoint/run/plan version bền vững | WorkflowRun, Postgres checkpointer, interrupt, decision ID/version và migration | Đã merge PR #44; suite test resume approval/data và stale version. Còn cần fault test kill/restart worker và kiểm tra cạnh tranh nhiều worker; G1/G4 chưa khép |
| R4 | Routine trong worker; PLAN_FROZEN dựng sau tính toán; rerun cùng process | Runner riêng; persist plan/start trước dispatch; ghi từng attempt; rerun execution độc lập | Kill/timeout vẫn giữ journal; kết quả âm được giữ; so manifest/checksum/tolerance; G5 |
| R5 | Critic chỉ đọc 3.000 ký tự đầu; protocol chưa đủ review gate | Review từng section với evidence/method/results; tổng hợp verdict; no-delta stop, citation repair dùng chung cap | Lỗi cuối bài bị phát hiện; nguồn bất đồng/thiếu evidence, protocol chưa đạt không phát hành như đã duyệt; G2/G4/G5 |
| R6 | PDF parse/embed ngay trong HTTP request; hard-delete rồi cleanup có thể bỏ qua lỗi | Ingest job riêng, READY gating; tombstone và cleanup retry | Timeout, upload trùng, xóa khi ingest/run, file mồ côi; G3/G6 |
| R7 | Một report/task; Q&A/report versions chưa đầy đủ | ReportVersion/base version, Q&A theo evidence của version; thay data/method tạo run mới | Giữ bản cũ, không dùng result lỗi thời; export đúng owner/version; G6 |
| R8 | Release image dùng dependency không khóa; Compose dev; chưa có deploy/restore gate | Release lockfile đã test, image bất biến; staging → production; readiness, backup/rollback | P8–P10 và checklist phát hành |

**Cập nhật 23/10 — R1 / issue #39:** đã sửa client auth/me và intake file; local có 98 backend tests và 5 frontend tests đạt. File thực địa hiện hỗ trợ CSV/TXT UTF-8 ≤5 MiB, có provenance và chỉ nhận artifact cùng task đã lưu/kiểm nội dung thành công. Chưa có trạng thái READY riêng trong schema; kiểm file tồn tại/đúng loại/kích thước/nội dung tại resume là điều kiện sẵn sàng hiện tại. PR #40 đã đạt 5/5 CI và merge develop tại baac5ba ngày 23/10; chưa đóng toàn bộ G1/G4 hoặc xác nhận browser E2E. Bảng R1 phía trên lưu vấn đề và nghiệm thu của đầu việc.

**Cập nhật 24/10 — R2 / issue #41:** giới hạn API theo SRS, đặt chỗ và đối chiếu ngân sách trong JSON task bền vững, tính từng lần thử LLM/fallback/embedding và mỗi truy vấn search, kiểm tra trạng thái/attempt/lease trước request, dừng khi hủy hoặc hết thời gian. Backend suite đạt **109 tests trên PostgreSQL/pgvector tạm**; Docker backend build và OpenAPI đạt. PR #42 đạt 5/5 CI và đã squash-merge vào `develop` tại `eacdb2b`. Không có provider thật trong lần kiểm này. Search mặc định tính 0.01 USD/request để ước lượng; phải đối chiếu với gói Tavily đang dùng trước pilot, nên đây chưa phải bảo đảm hóa đơn chính xác. PDF upload chỉ chia/lưu chunks cục bộ; embedding được tạo trong workflow có ngân sách.

**Cập nhật 24/10 — R3 / issue #43:** thêm `workflow_runs`, PostgreSQL LangGraph checkpointer, interrupt/resume cho duyệt kế hoạch và nạp kết quả, `plan_version` cùng quyết định có version. Worker đóng checkpointer sau mỗi lần chạy; test resume khôi phục state qua một graph/checkpointer mới. Backend suite đạt **109 tests** trên DB PostgreSQL/pgvector tạm; backend/frontend/Compose build đạt; PR #44 đạt **5/5 CI** và merge vào `develop` tại `b2e39b7`. Chưa chạy provider thật, kill worker giữa execution hoặc thử nhiều worker đồng thời; G1/G4 chưa khép.

**R1–R3 đã merge; tiếp theo R5 / issue #45** để khép review toàn bài và chạy REVIEW E2E trong cap. Sau đó R4 xử lý runner/journal thực nghiệm; R6/R7 theo thứ tự phụ thuộc. Chia mỗi hàng thành issue/PR nhỏ khoảng 1–2 ngày làm việc.

**Khép sai khác contract:** R2 thống nhất server/schema/UI/tests với cap SRS (40 LLM calls, 2 USD ước tính, 15 phút active/run). R4 thống nhất CSV 5 MiB/20.000 hàng/30 cột; hiện code nhận giới hạn 10 MiB/10.000 hàng/51 cột. Không nâng số hàng trước khi đo runner 120 giây; khi chưa hỗ trợ phải từ chối rõ ràng và chưa đóng G5. R6/R8 xử lý cache riêng tư theo owner/task/version hoặc tắt cache đó, bao gồm invalidation khi xóa; không chỉ xóa file gốc.

## 4. P0–P7: phần còn lại và ước lượng

Không xây lại phần đã có. Các số dưới là **ước lượng trước khi R3 hoàn tất (23/10)** cho phần việc được liệt kê, gồm test/review cơ bản, chưa gồm 20% dự phòng hoặc chờ provider/hạ tầng. Đo lại tổng giờ còn lại ngày 25/10 sau khi chốt phạm vi R5/R4.

| Chặng | Đã có code | Phần còn lại | Phụ thuộc | Giờ | Gate |
|---|---|---|---|---:|---|
| P0 — nền tảng | Docker, migration sạch, DB test riêng, lock dev/CI | Duy trì bằng chứng revision/config | — | 0–2 | G0 đã kiểm lại 22/10 |
| P1 — quyền/lifecycle | Auth, owner, outbox, lease/recovery, quota RUNNING, cancel/delete | R1/R2/R3 đã merge; fault test kill/restart worker, nhiều worker và late-write | P0 | 8–12 | G1 đầy đủ |
| P2 — REVIEW có căn cứ | Web/evidence/writer/critic/citations/AgentRun | R2 budget, R5 toàn bài/no-delta, provider smoke có cap | P1 | 12–18 | G2 với provider thật |
| P3 — PDF/workspace | PDF/artifacts, UI nối nhiều API, polling | R6 ingestion, READY/embedding scope, browser E2E web+PDF | P1/P2 | 6–10 | G3 |
| P4 — approval/human-led | Approval, protocol, WAITING_USER_DATA, R1 intake, R3 checkpoint/version | R5 protocol review; fault test restart/concurrency | P1; plan/evidence P2 | 12–18 | G4 qua restart |
| P5 — thực nghiệm | Routine regression, metrics/journal, kiểm lặp | R4 runner/journal/rerun, provenance human-led, artifact integrity | P2/P4 | 16–24 | G5 |
| P6 — hỏi/sửa/xuất | Xem report, tải artifact cơ bản | R7, export Markdown/gói thực nghiệm; R6 deletion/retention | P2/P4/P5 | 10–16 | G6 |
| P7 — đánh giá/bản nộp | Có thiết kế evaluation | Freeze dataset/rubric, baseline/ablation, browser/runtime QA, báo cáo kết quả | Các gate tương ứng | 10–16 | G7 |
| **Tổng (ước lượng 23/10, trước R3)** | | | | **74–116** | **Khoảng 89–140 giờ có 20% dự phòng; cần cập nhật 25/10** |

### Lịch mục tiêu đến 10/11

23/10 đến 10/11 cách nhau 18 ngày. Giả định 3–4 giờ/ngày cho khoảng 54–72 giờ, **chưa đủ chắc chắn cho 89–140 giờ ước lượng**. Đây là rủi ro tiến độ, không phải cam kết mọi gate sẽ kịp.

| Khoảng thời gian | Ưu tiên điều phối | Điểm kiểm soát |
|---|---|---|
| 23–25/10 | R1/R2/R3 đã merge; khóa contract run/budget và kiểm resume | 109 backend tests; còn cần fault test restart/worker concurrency |
| 26/10–01/11 | REVIEW/R5, provider smoke có cap, upload | Critic review cả bài; bài REVIEW qua UI; restart/resume và nhiều bài không lẫn nhau |
| 02–05/11 | R4; protocol/data path và ingestion | Execution riêng; human-led chỉ hoàn thành khi đủ dữ liệu |
| 06–09/11 | R7/R6 nếu dependency đạt; evaluation/sửa blockers ưu tiên | Freeze candidate và evidence trên cùng revision |
| 10/11 | Demo/bàn giao | Không thêm feature; báo gate đạt/chưa đạt |

Đo lại thời gian còn lại vào **25/10 và 01/11**. Thiếu thời gian thì giữ quality gate, dời nghiệm thu phần chưa xong và công khai trong báo cáo; không âm thầm xóa FR khỏi SRS hoặc mock thí nghiệm. Phần chưa đạt không được quảng bá/bật cho người ngoài. PDF đẹp/ảnh/OCR không nằm trên đường găng. Việc chốt plan là chốt hướng và thứ tự, không xác nhận deadline đã khả thi.

## 5. Từ bản nộp đến production

Production là mốc sau nghiệm thu chức năng, **không đồng nhất với 10/11**. Đích đầu tiên đủ nhỏ để một người vận hành; chưa có bằng chứng tải thì chưa phân tán thêm.

| Chặng | Đầu vào | Công việc | Ước lượng | Cổng kết thúc |
|---|---|---|---:|---|
| P8 — staging giống môi trường thật | Candidate với G0–G7 đạt | FE/API/worker release images; TLS; private DB/Redis/storage; runner riêng; secrets; backup/restore; metrics; migration/release | 20–30 giờ | GP8: fresh install, upgrade, restore DB+files, rollback app, smoke 3 luồng qua UI |
| P9 — dùng thử giới hạn | GP8 | Invite-only khoảng 5–10 người; quota/support/deletion; load/fault tests; chi phí/chất lượng thực; quan sát ít nhất 7 ngày | 12–20 giờ công + quan sát | GP9: không lỗi nghiêm trọng quyền/data loss/kết quả giả; đạt tải đã đo, xử lý phản hồi |
| P10 — production giới hạn | GP9; Chiến quyết định go/no-go | Chốt cost ceiling/retention/vận hành; diễn tập sự cố; release có rollback; tăng quota từng bước | 8–12 giờ công + cửa sổ release | GP10: checklist §8 đạt, kiểm sau deploy, có người nhận alert |

Sau P7 còn **40–62 giờ**, khoảng 48–75 giờ có dự phòng, cộng thời gian quan sát. Chỉ đặt ngày production khi P7 đạt và biết môi trường/chi phí; không tự mua dịch vụ. Chỉ phục vụ mức tải đã kiểm, không mở công khai không giới hạn.

### Hạ tầng và CI/CD cần hoàn thiện ở P8

1. **Topology:** HTTPS reverse proxy → FE/API; DB/Redis mạng riêng; worker và runner tách execution; bucket private. Một VPS có thể đủ cho pilot nếu đo tài nguyên, công khai điểm lỗi đơn. DB managed tùy ngân sách; chưa cần Kubernetes.
2. **Cấu hình/auth:** production từ chối secret mặc định, DEBUG=false, không reload/source mount; CORS allowlist, upload/request limit, auth rate limit. Chốt session production trước pilot: ưu tiên HttpOnly/Secure cookie cùng origin, CSRF protection khi dùng cookie. Nếu chưa có refresh/revoke thì session hết hạn phải dẫn đăng nhập lại rõ ràng.
3. **Dữ liệu:** owner-scope file/cache/retrieval; pin embedding model/dimension; không log toàn prompt/nguồn riêng. Tombstone chặn ngay, cleanup ≤24 giờ, backup retention ≤7 ngày theo SRS. Restore phải áp lại deletion ledger để không phục hồi quyền đọc dữ liệu đã xóa.
4. **CI:** full backend tests, FE lint/build + browser tests, migration DB rỗng và bản release trước, secret/dependency/container scan và licenses. Không tự nâng major để xóa cảnh báo; xử lý theo ảnh hưởng thực tế.
5. **CD:** build bằng lockfile, ghi SHA/digest; staging nhận artifact bất biến; smoke/integration/provider có cap; promotion **cùng digest** lên production qua environment gate. Hiện Action chỉ publish backend image, chưa có chuỗi này.
6. **Migration/rollback:** backup; expand–migrate–contract giữ tương thích bản app trước; một migration job. Rollback app về digest trước, không tự downgrade phá dữ liệu. Restore cần dừng ghi, phục hồi DB+files cùng mốc và reconcile outbox, không replay mù mọi job.
7. **Secrets:** tách dev/staging/prod, quyền tối thiểu, rotation; không nhúng key vào image. GitHub environments tách secrets/protection theo gói tài khoản thực tế, theo [tài liệu GitHub](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

Upload phải kiểm type/signature/size/parser/authorization/storage nhiều lớp, theo [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html). Không phục vụ file riêng bằng URL công khai.

### Vận hành và mục tiêu đo ở P9–P10

Các số dưới là **mục tiêu ban đầu, chưa phải SLA đạt được**. Dashboard dùng metrics collector/Grafana hoặc dịch vụ tương đương; không xây một hệ thống quan sát quá lớn.

| Chỉ số | Mục tiêu ban đầu | Xử lý khi không đạt |
|---|---|---|
| API CRUD/list/status | p95 <500 ms, server error <1%, test 30 phút với 10 phiên UI và 2 workflow; tách provider/ingestion khỏi request | Lưu cấu hình máy/data/tải; giảm quota hoặc sửa bottleneck và đo lại |
| Job lifecycle | Không mất job/output trùng trong bộ crash/retry; WAITING không giữ slot | Alert queue age >5 phút/lease hết; phân biệt đợi quota với lỗi dispatch |
| Availability | 99,5%/30 ngày sau khi đủ quan sát | Pilot 7 ngày không chứng minh SLA tháng; ghi outage/cách phục hồi |
| Cost | Server cap theo SRS: ≤2 USD ước tính/run, ≤40 LLM calls/run; chốt thêm cap ngày/user/toàn deployment trước pilot | Không biết giá/usage thì chặn paid call; alert 80%, ngừng cấp ở 100%; thêm quota phía provider |
| Runner | 1 job/runner, 2 CPU, 1 GiB, 120 giây; network off, output ≤20 MiB | Timeout/OOM giữ attempt lỗi, không tạo Results, retry hữu hạn |
| Backup | RPO ≤24 giờ (dữ liệu tối đa có thể mất), RTO ≤4 giờ (khôi phục) | Backup hằng ngày private/encrypted; diễn tập restore riêng, ghi thời gian thực |
| Data/quality | Không leak chéo owner, fabricated Results hoặc citation reference chưa giải quyết trong bộ nghiệm thu | Chặn release, khóa đường lỗi và giữ evidence |
| Người vận hành | Chiến nhận alert lỗi/cost/disk/backup; runbook Redis/provider/worker/DB/storage lỗi | Có công tắc ngừng nhận job, triage và kiểm phục hồi; không retry vô hạn |

## 6. Ma trận kiểm tra trước khi coi chức năng ổn

| Nhóm | Ca bắt buộc | Bằng chứng |
|---|---|---|
| Auth/ownership | Token hết hạn, auth/me, truy cập chéo task/report/artifact/events, rate limit | API + browser, log không có token |
| Lifecycle | Start/resume lặp, broker lỗi trước/sau publish, kill worker sau side effect, stale lease/cancel/delete | DB/broker/worker staging riêng; một active run, output đúng version |
| Nhiều bài | A/B/C WAITING, D chạy; đủ 2 RUNNING thì E QUEUED; resume lúc hết slot | UI/API, restart không mất workspace |
| Review/quality | No-source, mâu thuẫn, injection web/PDF, citation giả, lỗi cuối bài, no-delta, hết budget | Fake deterministic + live smoke; semantic support đo riêng FK validation |
| Upload/intake | Quá lớn/sai type/malformed, timeout; thiếu provenance/file READY/owner; upload/resume trùng | DB/artifacts riêng, không dữ liệu nhạy cảm |
| Experiment | CSV đúng/sai, leakage, constant target, NO_IMPROVEMENT, timeout/kill, rerun riêng | Manifest/hash/code/image/seed/metrics/diff; giữ lỗi và kết quả âm |
| Revision/delete | Q&A đúng version; edit giữ bản cũ; đổi data không dùng Results cũ; delete khi chạy | HTTP/browser + DB/storage; cleanup không tái tạo file |
| Release/ops | Fresh install/upgrade/rollback/restore, load, alert thực sự gửi được | Cùng digest phát hành; expected/actual/ngày và log đã che dữ liệu |

Evaluation khoa học theo [Evaluation Plan](evaluation-plan.md): pilot 4 câu riêng; held-out 8 câu × 3 cấu hình cùng corpus/model/cap; đo support/coverage/integrity/cost/latency/failures. So multi-agent đầy đủ với single-agent và multi-agent **tắt macro loop nhưng giữ micro revision**. Không so mock với model thật, không suy SLA từ vài run; công khai giới hạn mẫu nhỏ/chấm một người.

## 7. Quy trình thực hiện

1. Chọn việc đầu tiên chưa đạt trong R1–R8/P8–P10. Issue ghi vấn đề người dùng, phạm vi, acceptance, FR/NFR/gate và ngoài phạm vi.
2. Branch từ develop: feature/<issue>-<slug>, bugfix/<issue>-<slug>, docs/<slug> hoặc chore/<slug>; không tên người/AI/công cụ. Một nhánh code hoạt động tại một thời điểm.
3. Triển khai lát cắt → tests → review diff → sửa → PR develop. Test DB/artifacts riêng, không dùng DB dev/production.
4. Ghi SHA, môi trường, lệnh/thao tác, expected/actual, provider thật/giả, giới hạn; cập nhật đúng hàng Roadmap. Không tạo nhiều báo cáo trùng nhau.
5. CI xanh là cần nhưng chưa đủ: develop → main chỉ khi full tests và demo UI/API/queue/provider thật trên cùng candidate đạt. Theo [CONTRIBUTING](../../CONTRIBUTING.md).

## 8. Checklist chốt release

- [ ] G0–G7 đạt trên cùng candidate; không còn R1–R7 chưa giải quyết trong chức năng công bố.
- [ ] Không lỗi nghiêm trọng auth/data loss/chi phí/Results giả/late write.
- [ ] Migration tương thích, release dùng lockfile, runtime/provider profile được pin.
- [ ] GP8 staging/restore/rollback/alert và GP9 pilot đạt trước GP10.
- [ ] Docs/UI mô tả đúng tính năng mở, giới hạn, cách xóa dữ liệu và trách nhiệm kiểm tra của người nghiên cứu.
- [ ] Chiến quyết định go/no-go theo evidence; main/tag cùng artifact đã kiểm; health/smoke sau deploy đạt.

**Chốt planning:** giữ hướng sản phẩm và kiến trúc, ưu tiên tính đúng/phục hồi/đo được của chức năng hiện tại. R1–R3 đã merge; tiếp theo R5 review toàn bài, rồi R4 runner/journal theo dependency. Chưa đủ điều kiện chốt phát hành production.
