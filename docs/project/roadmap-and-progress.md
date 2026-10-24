# Roadmap và tiến độ — Synthia

**Cập nhật:** 24/10/2026 · **Baseline đã merge:** develop@b2e39b7 · **Hạn nộp/demo:** 10/11/2026.

### Đã hoàn thành R1 / issue #39

Branch `bugfix/39-authenticated-fieldwork-intake`: sửa xác thực profile và tiếp nhận kết quả thực địa. API/UI đã có upload CSV/TXT riêng, bắt buộc provenance/file đúng owner/task, lưu UUID dạng JSON và snapshot/hash của dữ liệu do người dùng cung cấp. Upload không tự resume; resume lặp bị chặn bằng row lock/state. **98 backend tests + 5 frontend tests đạt local**; [PR #40](https://github.com/NguyenChien536/Multi-Agent-Research-System/pull/40) đạt 5/5 CI và đã merge vào develop ngày 23/10, commit baac5ba. Issue #39 đã đóng. Đây là sửa một phần G1/G4, không phải nghiệm thu toàn bộ các gate. Bảng audit 22/10 bên dưới là trạng thái baseline trước sửa; lỗi auth/me và UUID/intake đã được xử lý trên branch này.

### Đã hoàn thành R2 / issue #41

PR #42 đã merge vào `develop` tại `eacdb2b`. R2 chặn LLM, search và embedding trước request bằng usage/reservation trong task; retry/fallback tính riêng, task bị hủy/stale/lease hết hạn không qua bước tiếp theo. Schema giới hạn theo SRS: 40 LLM calls, 2 USD ước tính, 100k input tokens, 50k output tokens, 15 phút hoạt động. **109 backend tests đạt** trên DB test riêng; CI đạt 5/5, Docker backend build và OpenAPI đạt. Provider được giả lập; chưa chạy browser hoặc provider thật. Search mặc định ước tính 0.01 USD/request và cần đối chiếu giá gói trước pilot. PDF được chia chunks tại upload; embedding chạy trong workflow có ngân sách.

### Đã hoàn thành R3 / issue #43 — bước kế tiếp R5 / issue #45

PR #44 đã squash-merge vào `develop` tại `b2e39b7`; issue #43 đã đóng. Mỗi lần thực thi có `WorkflowRun`/checkpoint thread riêng; LangGraph Postgres saver lưu state qua lần gọi worker, còn API chỉ resume quyết định đúng `plan_version`. Approval và chờ dữ liệu thực địa/CSV dùng interrupt, worker kết thúc trong lúc chờ và tiếp tục từ checkpoint khi có input. Backend suite **109 passed** trên PostgreSQL/pgvector tạm; GitHub CI **5/5** (backend tests, syntax, frontend build, Compose build, branch policy). Test khôi phục checkpoint bằng graph/checkpointer mới, nhưng chưa kill/restart Celery process giữa một execution và chưa thử nhiều worker đồng thời. Provider thật và browser E2E cũng chưa chạy. Đây là phần đã triển khai, không phải nghiệm thu đầy đủ G1/G4.

Tài liệu này trả lời **đã làm đến đâu và đã kiểm tra gì**. Thứ tự, lịch và ước lượng chỉ đặt tại [Implementation Plan](implementation-plan.md). Mỗi chặng có nhiều issue; merge code không tự làm gate của cả chặng đạt.

## 1. Kết luận hiện tại

- Nền tảng local hoạt động; backend có **109 tests đạt** trên DB PostgreSQL/pgvector tạm; PR #44 CI **5/5 đạt**.
- R1–R3 đã merge vào `develop`; code đã tiến qua nhiều phần P1–P5 nhưng các gate chưa được nghiệm thu toàn bộ.
- Có lỗi tái hiện được và khoảng cách giữa code với SRS. **Chưa thể xác nhận toàn bộ chức năng ổn định, chưa đủ điều kiện release lên main/production.**
- Lần kiểm R3 dùng provider giả và DB tạm; chưa chạy research với provider thật, browser E2E hay kill/restart worker giữa execution. Không lấy HTTP 200/build thành công thay cho E2E.

## 2. Trạng thái theo chặng

| Chặng | Đã triển khai | Bằng chứng | Phần chưa đạt / gate |
|---|---|---|---|
| P0 — môi trường | Runtime, migration, DB test riêng, lockfile dev/CI | 22/10: DB rỗng migrate head; 24/10: R3 migration trên DB tạm, backend/frontend/Compose build đạt | G0 nền tảng đạt; release Dockerfile còn lệch lockfile, xử lý R8 |
| P1 — quyền và vòng đời | Login/ownership; outbox/worker claim/lease; quota RUNNING; R1 intake; R2 budget/cancel; R3 checkpoint/resume | PR #40, #42, #44 đã merge; R3 CI 5/5 và backend 109 passed | G1 chưa khép: fault test kill/restart, nhiều worker, release E2E và deletion/late-write review còn thiếu |
| P2 — tìm nguồn và REVIEW | Search/fetch/embed; evidence/claims/citations; Writer/Critic; AgentRun | Các PR #17–#26; R2 budget guard đã merge; fake-provider integration đạt | G2 chưa khép: review toàn bài, no-delta và provider E2E trên candidate hiện tại chưa chạy lại |
| P3 — PDF và workspace | PDF/artifacts; UI gọi API, polling/task detail | PR #28; tests upload/ownership; frontend local build đạt | G3 chưa khép: ingest còn trong request, browser E2E và parser execution boundary |
| P4 — approval và human-led | Plan approval, protocol, WAITING_APPROVAL/WAITING_USER_DATA, intake/resume | PR #30/#32/#44; R3 resume theo checkpoint và plan version, test backend đạt | G4 chưa khép: kill/restart worker, nhiều worker và protocol review đầy đủ |
| P5 — thực nghiệm | Regression routine, AnalysisRun, journal append-only, metrics/kiểm lặp | PR #34/#36; tests leakage/âm/lỗi/integrity | G5 chưa khép: routine trong worker; journal ghi sau tính toán; chưa rerun execution riêng; cần thống nhất giới hạn CSV |
| P6 — hỏi/sửa/xuất | Xem report và tải artifact cơ bản | Có endpoints tương ứng | G6 chưa đạt: report versions/Q&A; package export và tombstone/cleanup policy chưa đủ |
| P7 — evaluation | Có thiết kế và rubric | Evaluation Plan | G7 chưa đạt: chưa có benchmark baseline/ablation được nghiệm thu; chưa đủ G1–G6 |
| P8–P10 — production | Có CI và workflow publish backend image | CI develop hiện xanh | Chưa triển khai staging/CD/restore/pilot; chưa đạt GP8–GP10 |

“Có test” ở đây chỉ xác nhận những tình huống test bao phủ, không chứng minh tất cả nghiệm thu của chặng. Các issue/PR lịch sử đánh dấu G4/G5 không thay thế review theo SRS đầy đủ.

## 3. Bằng chứng gần nhất

| Ngày / revision | Kiểm tra | Kết quả và giới hạn |
|---|---|---|
| 12/10 — lịch sử | Baseline dependencies/runtime/migration | Giữ tại biên bản; không dùng head/count cũ để mô tả hiện tại |
| 18/10 — lịch sử | Biên bản ghi một provider run thật với task ec0de102-517f-4706-ae51-d46d21e7987e | 22/10 đọc DB vẫn thấy COMPLETED, 1.325 từ, 9 citations, **0 AgentRun** cho task đó. Xác nhận report còn lưu; chưa kiểm lại provider/model/chi phí hay toàn bộ lineage của lần chạy lịch sử |
| 22/10 — c343da8 / PR #36 | Sửa empirical integrity và safe fetching | Đã merge develop; nằm trong regression suite hiện tại |
| 22/10 — 3bbeb01 / PR #38 | Phục hồi job QUEUED đã gửi nhưng worker chưa nhận | Đã merge develop; recovery có giới hạn thời gian/số lần, không replay mọi task cũ |
| 22/10 — [CI 39783342134](https://github.com/NguyenChien536/Multi-Agent-Research-System/actions/runs/39783342134) | Branch policy, backend syntax/tests, frontend build, Compose build | **5/5 đạt** trên commit 3bbeb01; không bao gồm thay đổi frontend local chưa commit |
| 22/10 — workspace hiện tại | DB rỗng → migration d1e2f3a4b5c6; pytest toàn bộ | **74 passed, 6 warnings, 24,37 giây**; DB test/artifacts tạm tách biệt và được dọn; provider giả |
| 22/10 — workspace hiện tại | FE lint/build; Compose config; API/frontend HTTP; Redis/Celery; DB revision | Đạt; API health/login page 200, Redis PONG, worker pong, queue broker 0; health chưa kiểm readiness dependencies |
| 22/10 — probe bổ sung | auth/me client và intake dữ liệu thực địa | **Phát hiện lỗi** ngoài 74 tests; xem R1 và biên bản, chưa sửa source trong đợt audit này |
| 24/10 — PR #44 / develop@b2e39b7 | Migration `e2f3a4b5c6d7`, durable workflow checkpoint, approval/data resume, stale-version rejection | Backend **109 passed** trên PostgreSQL/pgvector tạm; CI **5/5**; graph/checkpointer mới khôi phục state. Chưa thử kill/restart process, nhiều worker, browser E2E hoặc provider thật |

DB dev chứa nhiều dữ liệu thử lịch sử; có một task QUEUED trong lúc broker queue rỗng và nhiều PLANNING/WAITING cũ. Không tính tỷ lệ COMPLETED của DB này thành chất lượng sản phẩm. Cần đối soát owner/run/outbox/lease và nguyên nhân trước khi đổi trạng thái hoặc replay; audit chỉ đọc, không tự chạy/xóa các bài đó.

## 4. Việc tiếp theo theo thứ tự

1. **R5 / issue #45:** review toàn bài; khép REVIEW thực với provider trong cap.
2. **R4/R6/R7:** runner/journal độc lập, ingestion/deletion, Q&A/versions; nghiệm thu từng lát cắt theo phụ thuộc.
3. **P7 → P8 → P9 → P10:** đánh giá → staging/restore → pilot → production giới hạn theo plan.

Issue [#35](https://github.com/NguyenChien536/Multi-Agent-Research-System/issues/35) còn Open dù PR #36 đã merge; khi tổng kết issue cần đối chiếu acceptance trước khi đóng. Không tạo lại chức năng đã có vì nhãn issue chưa cập nhật.

## 5. Quy tắc cập nhật

Một hàng chỉ được chuyển sang **Verified** khi ghi được revision, môi trường, lệnh/thao tác, expected/actual và giới hạn; phân biệt provider thật/giả. Gate đã đạt nhưng phát hiện regression phải mở lại. Ngày mục tiêu/giờ công cập nhật ở [kế hoạch](implementation-plan.md), không sao chép lịch vào nhiều file.
