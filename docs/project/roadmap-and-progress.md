# Roadmap và tiến độ — ATI

**Cập nhật:** 12/10/2026 · **Kỳ hạn:** 10/09–10/11/2026.<br>
Định hướng: Multi-Agent Research tạo bài báo có bằng chứng và thực nghiệm tái lập. Nguồn chi tiết: [User Journey](user-journey-and-outputs.md), [Implementation Plan](implementation-plan.md), [SRS v4.1](../requirements/SRS.md), [Evaluation Plan](evaluation-plan.md).

## 1. Mốc đã có bằng chứng

| Mốc | Bằng chứng | Cách hiểu |
|---|---|---|
| 10/09–24/09 | Hồ sơ đề tài/planning phát triển trong giai đoạn đầu | Không suy ra code đã hoàn thành từ tài liệu |
| 27/09, biên bản 28/09 | Docker/DB/API/worker ping/graph compile và routing mẫu trong baseline log | Chỉ xác minh những lệnh đã ghi, chưa research E2E |
| Source `ebb525a`, đọc 08/10 | Register, ClaimEvidence/Citation migration đã commit; graph/search/retrieval/Writer có source | DB hiện tại và feature runtime sau baseline chưa được xác minh |
| 08–09/10 | Rà scope/code, chốt SRS v4.1, ADR-004, luồng nhiều bài và kế hoạch/evaluation | Planning đã được cập nhật; không phải implementation đã nghiệm thu |
| 12/10 | P0: đồng bộ Python 3.11; lock dependencies; clean-DB migration đến `a1b2c3d4e5f6`; backend 2 tests pass; Celery `pong`; API health 200; frontend lint/build pass | G0 verified cho baseline. Research/provider E2E vẫn chưa được chạy; xem [biên bản kiểm tra](baseline-verification.md) |

## 2. Mục tiêu đến 10/11

Ba đường đều nhắm **bài báo hoàn chỉnh**: REVIEW web+PDF có citation; EMPIRICAL_COMPUTATIONAL với một CSV routine chạy thật và gói tái lập; EMPIRICAL_HUMAN có protocol trung gian, pause/upload/resume rồi viết bài sau khi có kết quả thật. Mỗi bài có workspace riêng; A chờ không cản B. Q&A/sửa phiên bản, progress/log, auth/ownership/budget dùng chung. Tổng quan và human-led nhận nhiều lĩnh vực; execution tự động giới hạn method/schema hỗ trợ.

Experiment không còn là phần “nếu kịp”. Nếu không đạt gate phải ghi thiếu so với mục tiêu; không thay bằng mock và nhận đã xong. Ảnh, PDF trình bày đẹp, nhiều routine, OCR, arbitrary-code sandbox và cộng tác nhóm để sau.

## 3. Lịch còn lại

Ước lượng dựa trên giả định Chiến dành 3–4 giờ tập trung/ngày; chưa phải cam kết năng lực đã đo. P0 hoàn thành ngày 12/10, trễ hai ngày so với lịch cũ; các mốc sau đã dời tương ứng và cần chốt lại velocity sau P1.

| Thời gian | Gói triển khai của Chiến | Gate |
|---|---|---|
| 12/10 | P0 — baseline tái lập, dependency/DB/test isolation | **G0 Verified** |
| 13–16/10 | P1 — auth, nhiều task/user, ResearchRun, lifecycle/outbox/events/quota | G1 |
| 17–21/10 | P2 — web E2E, evidence, Writer/Critic/Validator, budget | G2 |
| 22–25/10 | P3 — PDF, dashboard nhiều bài, evidence/progress | G3 |
| 26–28/10 | P4 — plan/protocol trung gian, assisted/automatic, durable waits/resume | G4 |
| 29/10–01/11 | P5 — experiment thật, human-led result intake, empirical manuscripts | G5 |
| 02–04/11 | P6 — Q&A/revision, authorized export, delete/cleanup | G6 |
| 05–09/11 | P7 — baseline/ablation, QA, sửa blockers, báo cáo | G7 |
| 10/11 | Buffer, freeze, demo/backup/nộp bài | Không thêm feature |

Thứ tự phụ thuộc và giờ ước lượng từng gói ở [Implementation Plan](implementation-plan.md). Không thể bỏ auth/provenance để “xong UI trước”. Khi trễ, cắt polish/ảnh/PDF đẹp; giữ kết quả thật và báo trung thực gate còn thiếu.

G0–G7 có một định nghĩa thống nhất tại [SRS §8](../requirements/SRS.md#8-acceptance-gates); FR/NFR được nối sang gói triển khai ở mục 9. Hiện G0 đã Verified; G1–G7 chưa đủ evidence. Khi cập nhật tiến độ, dùng Planned / In progress / Implemented / Verified / Blocked kèm revision, ngày và link kết quả; không tự chuyển mốc kế hoạch thành ngày đã hoàn thành.

## 4. Việc chuẩn bị song song của Chiến

| Hạn chuẩn bị | Artifact | Mục đích |
|---|---|---|
| 12/10 | 12 câu hỏi (4 pilot, 8 held-out), nguồn/expected points và rubric đóng băng | Đánh giá lợi ích multi-agent, không điều chỉnh held-out sau khi xem kết quả |
| 16/10 | CSV công khai + data dictionary/license/checksum | Thực nghiệm tính toán thật và tái lập |
| 17/10 | 4 kịch bản UI, gồm A chờ/B chạy/A resume; demo checklist | Kiểm user flow, trạng thái và recovery |
| 03–07/11 | Chấm ẩn nhãn, manual QA và issue log | Báo số thực đo, nêu hạn chế đánh giá một người |

## 5. Tiến độ source và runtime

| Hạng mục | Đọc source 08/10 | Evidence còn cần |
|---|---|---|
| API/DB/graph nền | 12/10: image build từ lock; clean-DB migration đến head; API health 200; Celery ping `pong`; 2 backend tests pass | Provider E2E, retry/recovery và full graph với input thật |
| Auth | 12/10: test register/login/current user, task ownership, list/get/start/report và chặn đọc chéo user | Security review sâu, session expiry/rate limits và dispatch failure |
| Web/PDF evidence | Web source có trong code; PDF chưa có đủ luồng | Provider E2E, ingest PDF và claim anchors |
| Writer/Critic/Validator | Writer/Critic có; validator placeholder | Full-report review, persisted lineage, bounded loops |
| Budget/idempotency | Chưa thực thi đầy đủ; start hiện gửi Celery sau DB commit | Reserve/reconcile, outbox, redelivery/restart và start idempotency gates |
| Protocol/wait/resume | Target mới; graph chưa checkpointer | Protocol trung gian, durable checkpoint + upload READY + đúng version; A chờ/B chạy |
| Routine/experiment | Chưa có đủ implementation | Actual CSV run, journal mọi attempt/kết quả âm, manifest + rerun có sai khác; human-led result provenance và bài hoàn chỉnh sau upload |
| UI/Q&A/report versions | Starter/polling; phiên bản/Q&A còn thiếu | Tương tác và feedback/end states thực tế |
| Evaluation | Đã có kế hoạch | Chưa đo; không có số quality/cost/superiority |

## 6. Sau bản nộp

| Hướng | Điều kiện mở rộng |
|---|---|
| Cá nhân dùng ổn định | Core gates đạt, retention/quota/recovery rõ, theo dõi chi phí thực |
| Nhiều phương pháp/ngành | Routine/template có validation riêng và người đánh giá phù hợp |
| Nhóm nghiên cứu | Workspace membership/roles/sharing/audit, cách ly dữ liệu, không chỉ thêm bảng users |
| Vận hành rộng | Threat model, secure sandbox nếu nhận code tự sinh, load/recovery/backup evaluation, privacy policy |
| Mã do AI sinh | Chỉ xét sau khi journal và kiểm tái lập được nghiệm thu, runner cô lập mã không tin cậy qua threat model/security review, benchmark chất lượng/chi phí/ca âm đủ mạnh; quyết định bằng ADR mới |

Không ấn định ngày mở rộng trước khi biết kết quả đánh giá. Mục tiêu dài hạn giữ đa lĩnh vực, còn chất lượng và khả năng tái lập quyết định method được hỗ trợ.
