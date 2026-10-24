# Roadmap và tiến độ — Synthia

**Cập nhật:** 24/10/2026 · **Baseline đã merge:** develop@baac5ba · **Hạn nộp/demo:** 10/11/2026.

### Đã hoàn thành R1 / issue #39 — tiếp theo R2

Branch `bugfix/39-authenticated-fieldwork-intake`: sửa xác thực profile và tiếp nhận kết quả thực địa. API/UI đã có upload CSV/TXT riêng, bắt buộc provenance/file đúng owner/task, lưu UUID dạng JSON và snapshot/hash của dữ liệu do người dùng cung cấp. Upload không tự resume; resume lặp bị chặn bằng row lock/state. **98 backend tests + 5 frontend tests đạt local**; [PR #40](https://github.com/NguyenChien536/Multi-Agent-Research-System/pull/40) đạt 5/5 CI và đã merge vào develop ngày 23/10, commit baac5ba. Issue #39 đã đóng. Đây là sửa một phần G1/G4, không phải nghiệm thu toàn bộ các gate. Bảng audit 22/10 bên dưới là trạng thái baseline trước sửa; lỗi auth/me và UUID/intake đã được xử lý trên branch này.

### Đang triển khai R2 / issue #41

Nhánh `feature/41-provider-budget-cancel-guards` chặn LLM, search và embedding trước request bằng usage/reservation trong task; retry/fallback được tính riêng, task bị hủy/stale không qua bước tiếp theo. Schema giới hạn theo SRS: 40 LLM calls, 2 USD ước tính, 100k input tokens, 50k output tokens, 15 phút hoạt động. **109 backend tests đạt** trên DB test riêng, Docker backend build và OpenAPI đạt. Chưa tạo PR/nhận CI; provider giả, chưa chạy browser hoặc provider thật. Search dùng mức ước lượng mặc định 0.01 USD/request và cần đối chiếu giá gói trước pilot. PDF được chia chunks tại upload; embedding chạy trong workflow để tính đúng vào budget.

Tài liệu này trả lời **đã làm đến đâu và đã kiểm tra gì**. Thứ tự, lịch và ước lượng chỉ đặt tại [Implementation Plan](implementation-plan.md). Mỗi chặng có nhiều issue; merge code không tự làm gate của cả chặng đạt.

## 1. Kết luận hiện tại

- Nền tảng local hoạt động; backend có **74 tests đạt**, frontend hiện tại lint/build đạt.
- Code đã tiến qua nhiều phần của P1–P5; thông tin cũ “P1 chờ PR #12, P2–P5 chưa bắt đầu” không còn đúng.
- Có lỗi tái hiện được và khoảng cách giữa code với SRS. **Chưa thể xác nhận toàn bộ chức năng ổn định, chưa đủ điều kiện release lên main/production.**
- Lần này kiểm bằng provider giả và đọc trạng thái runtime; chưa chạy lại research với provider thật hay thao tác UI trên trình duyệt. Không lấy HTTP 200/build thành công thay cho E2E.

## 2. Trạng thái theo chặng

| Chặng | Đã triển khai | Bằng chứng | Phần chưa đạt / gate |
|---|---|---|---|
| P0 — môi trường | Runtime, migration, DB test riêng, lockfile dev/CI | 22/10: DB rỗng migrate head; suite/lint/build đạt | G0 nền tảng đạt; release Dockerfile còn lệch lockfile, xử lý R8 |
| P1 — quyền và vòng đời | Login/ownership; outbox/worker claim/lease; quota RUNNING; R1 intake; R2 budget/cancel đang ở nhánh | PR #40 R1: 98 backend + 5 frontend, 5/5 CI; R2: 109 backend tests pass local | G1 chưa khép: R2 chưa qua PR/CI, release E2E/fault test và deletion/late-write review còn thiếu |
| P2 — tìm nguồn và REVIEW | Search/fetch/embed; evidence/claims/citations; Writer/Critic; AgentRun | Các PR #17–#26; fake-provider integration đạt; lịch sử 18/10 có report đã lưu | G2 chưa khép: budget guard, review toàn bài, no-delta; provider E2E trên candidate hiện tại chưa chạy lại |
| P3 — PDF và workspace | PDF/artifacts; UI gọi API, polling/task detail | PR #28; tests upload/ownership; frontend local build đạt | G3 chưa khép: ingest còn trong request, browser E2E và parser execution boundary |
| P4 — approval và human-led | Plan approval, protocol, WAITING_APPROVAL/WAITING_USER_DATA, intake/resume | PR #30/#32, tests luồng giả đạt | G4 chưa khép: UUID intake lỗi, thiếu evidence vẫn queue, chưa checkpoint/version bền vững hoặc protocol review đầy đủ |
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

DB dev chứa nhiều dữ liệu thử lịch sử; có một task QUEUED trong lúc broker queue rỗng và nhiều PLANNING/WAITING cũ. Không tính tỷ lệ COMPLETED của DB này thành chất lượng sản phẩm. Cần đối soát owner/run/outbox/lease và nguyên nhân trước khi đổi trạng thái hoặc replay; audit chỉ đọc, không tự chạy/xóa các bài đó.

## 4. Việc tiếp theo theo thứ tự

1. Hoàn tất **PR/CI R2** trên develop; main chưa được thay đổi.
2. **R3/R5:** resume bền vững và review toàn bài; khép REVIEW thực với provider trong cap.
4. **R4/R6/R7:** runner/journal độc lập, ingestion/deletion, Q&A/versions; nghiệm thu từng lát cắt.
5. **P7 → P8 → P9 → P10:** đánh giá → staging/restore → pilot → production giới hạn theo plan.

Issue [#35](https://github.com/NguyenChien536/Multi-Agent-Research-System/issues/35) còn Open dù PR #36 đã merge; khi tổng kết issue cần đối chiếu acceptance trước khi đóng. Không tạo lại chức năng đã có vì nhãn issue chưa cập nhật.

## 5. Quy tắc cập nhật

Một hàng chỉ được chuyển sang **Verified** khi ghi được revision, môi trường, lệnh/thao tác, expected/actual và giới hạn; phân biệt provider thật/giả. Gate đã đạt nhưng phát hiện regression phải mở lại. Ngày mục tiêu/giờ công cập nhật ở [kế hoạch](implementation-plan.md), không sao chép lịch vào nhiều file.
