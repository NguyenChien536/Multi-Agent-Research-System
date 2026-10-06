# Lộ trình, phân công và tiến độ ATI

> **Kỳ hạn nhóm đã chốt:** 10/09/2026–10/11/2026. Cập nhật planning ngày 06/10/2026 còn khoảng 5 tuần tới hạn; các mốc bên dưới là mục tiêu, không phải tiến độ đã xác minh. Baseline runtime gần nhất được ghi nhận 27/09 và tổng hợp 28/09.

## Quyết định sản phẩm hiện tại

ATI là research orchestrator/co-scientist có người giám sát; không chỉ tổng hợp web. Target gồm web + upload nguồn; candidate research questions/gaps; hypothesis/method/protocol; phân tích dữ liệu được hỗ trợ với output thật; paper theo loại nghiên cứu; progress/monitoring; bounded research/revision loops. Với lab/survey/field/human participants, ATI chỉ chuẩn bị protocol/ethics notice; nhà nghiên cứu tự xin review, thực hiện, rồi upload kết quả được phép xử lý. ATI không tuyển người hoặc tự khởi động nghiên cứu ngoài đời.

**Release gate:** trước 10/11 tập trung một luồng literature review đầu-cuối (web + PDF upload, evidence/citation, candidate gap, report, progress) và tối đa một computational experiment slice có routine/dataset an toàn, tái lập. Các phương pháp ngoài routine dừng ở protocol hoặc nhận kết quả do researcher cung cấp. Không hứa hỗ trợ mọi ngành/format; không tạo Results khi thiếu actual data. Image/PDF polished/collaboration là non-core.

## Vai trò và đầu ra

| Thành viên | Vai trò | Đầu ra không cần code | Hạn mục tiêu |
|---|---|---|---|
| **Nguyễn Đình Chiến** | Nhóm trưởng, planner, technical lead, developer duy nhất | Implementation; quyết định kỹ thuật; review nội dung kỹ thuật; command/result log, demo và risk | 10/09–10/11 |
| **Phạm Long Vũ** | Evaluation set và manual QA | 10–15 query có nguồn; rubric chấm claim/citation; một CSV nhỏ + data dictionary + expected checks nếu có experiment slice; manual QA | 12/10 query set v1; 26/10 dataset/rubric; 06/11 QA |
| **Nguyễn Văn Hiếu** | User scenarios và demo operations | 4 scenario: literature/PDF, plan review, external study wait/upload, analysis result; stage/warning copy review; demo checklist và issue log | 12/10 scenarios; 25/10 checklist; 06/11 demo |
| **Nguyễn Thị Hải My** | Research background, source quality, editorial | 8–12 nguồn học thuật/chính thống; related-work matrix; kiểm tra claims, consistency và references trong docs/report | 17/10 source matrix; 31/10 review; 07/11 editorial |

Vũ, Hiếu và My không nhận task coding, backend configuration, database hoặc code review. Họ tập trung research, evaluation, user flow, QA thủ công và biên tập.

## Kế hoạch đến 10/11

| Mốc | Chủ trì | Công việc / điều kiện hoàn tất |
|---|---|---|
| 06–09/10 | Chiến | Đóng planning: SRS/HLD/workflow/data model thống nhất; chốt demo slice, Definition of Done và scope freeze |
| 07–12/10 | Hiếu, Vũ | Scenarios + query set v1; Chiến chốt demo question |
| 07–13/10 | Chiến | Xác minh baseline sạch/migrations/auth ownership; chưa mở user thật khi access control chưa đạt |
| 13–20/10 | Chiến | Upload nguồn, ingestion/retrieval, claim/evidence lineage; mock-first E2E |
| 17–24/10 | My, Hiếu | Related-work/source matrix; flow/checklist; review usability |
| 21–29/10 | Chiến + Vũ | Writer/citation validation; một analysis routine/data fixture nếu safety gate đạt |
| 30/10–04/11 | Chiến | Bounded critic/research loop; WAITING_USER_DATA/protocol branch nếu kịp; progress logs/correlation |
| 05–07/11 | Cả nhóm | Chạy checklist, chấm evaluation sample, triage; không thêm feature mới |
| 08–10/11 | Chiến, My, Hiếu | Freeze/demo/backup; cập nhật progress, limitations, AI disclosure và báo cáo |

**Nếu trễ:** giữ auth/ownership → một research E2E → provenance/citation → đúng loại output → evaluation/demo. Tạm hoãn runner nếu chưa đạt safety gate; khi đó dừng ở protocol hoặc kết quả do researcher cung cấp. Tiếp theo hoãn SSE nâng cao, images, PDF polished và multi-template. Không cắt security/provenance và không tạo Results giả.

## Baseline progress có bằng chứng

| Hạng mục | Kết quả gần nhất đã ghi nhận | Giới hạn |
|---|---|---|
| Docker/Compose | Config/build/start thành công; backend/worker/Postgres/Redis chạy; DB/Redis healthy | Development, chưa load/recovery/security |
| PostgreSQL/pgvector/Alembic | Postgres 16.15, vector extension, current revision 5ee074153cf3 | Volume đã có dữ liệu; DB rỗng chưa thử |
| FastAPI/task API | Health/OpenAPI HTTP 200; POST + GET task thành công | Task thử đã xóa; auth/owner chưa có; routes khác chưa thử |
| Celery | Worker ping trả pong | Chưa gửi workflow task thật |
| LangGraph | Graph compile; 5 router cases mẫu pass | Chưa invoke graph/provider thật |
| Search/retrieval/report | Có source code | E2E và citation/data lineage chưa nghiệm thu |
| Frontend/SSE | Frontend starter; polling/stream stub trong source | Chưa run UI/SSE E2E |
| Upload/analysis runner/WAITING_USER_DATA | Chưa có bằng chứng baseline | Chưa xác minh/triển khai |

Chi tiết: [baseline-verification.md](baseline-verification.md). Trạng thái Verified cần command/result/test artifact, ngày và người xác nhận. “Có source code” là implemented/unverified, không phải done. Không gọi provider thật nếu chưa có quota/cost cap.

## Giai đoạn sau demo: người dùng và năng lực

| Giai đoạn | Người dùng | Mở rộng | Gate |
|---|---|---|---|
| Demo/MVP | Cá nhân, task riêng | Một workflow review + web/upload + provenance; tối đa một analysis slice an toàn | E2E, ownership, bounded budget, evaluation |
| Sau MVP | Nhà nghiên cứu cá nhân/chuyên gia | Article templates/methods, routines, protocol/resume, export/images, observability | Acceptance, privacy/security review |
| Nhóm/tổ chức | Nhóm nghiên cứu và tổ chức | Collaboration, roles, tenant isolation, audit, retention/deletion | Threat model, privacy/legal review, operational support |

Hướng dẫn giao việc chi tiết: [team-task-guide.md](team-task-guide.md).
