# Tài liệu dự án ATI

**Bản chốt planning: 08/10/2026 — SRS v4.0.** ATI là hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập. Tài liệu mục tiêu tách riêng source inventory và runtime evidence.

## Đọc để bắt đầu triển khai

1. [Product Assessment](project/product-assessment.md) — kết luận hướng đi, findings và những quyết định đã sửa.
2. [SRS](requirements/SRS.md) — phạm vi, chức năng, giới hạn và nghiệm thu.
3. [Implementation Plan](project/implementation-plan.md) — P0–P7, dependency, lịch/giờ và gate; bắt đầu ở P0.
4. [Evaluation Plan](project/evaluation-plan.md) — cách kiểm chứng ích lợi multi-agent, ablation và thực nghiệm tái lập.
5. [ADR-004](architecture/decisions/ADR-004-multi-agent-research-delivery.md) — quyết định kiến trúc/phạm vi đã chốt.

## Dành cho giảng viên và nhóm

- [Báo cáo giữa kỳ](project/midterm-report.md): đủ Overview, Problems/Objectives, Technical Approaches, System Design, Development Plan, Progress và AI Disclosure.
- [Roadmap và tiến độ](project/roadmap-and-progress.md): lịch 10/09–10/11, evidence hiện tại, giai đoạn sau.
- [Phân công chi tiết](project/team-task-guide.md): Vũ/Hiếu/My làm nguồn, đánh giá, scenarios và biên tập; Chiến chịu trách nhiệm kỹ thuật.
- [AI Disclosure](project/ai-disclosure.md): đóng góp ghi nhận và phần còn cần xác nhận.
- [Baseline verification](project/baseline-verification.md): lệnh/kết quả lịch sử; không phải chứng nhận research E2E.

## Dành cho kỹ thuật

- [System Design](architecture/system-design.md): nguồn Mermaid chuẩn — kiến trúc, logical DFD, inference, async sequence, ERD; physical DFD và class appendix.
- [HLD](architecture/system-architecture.md): lý do chọn thành phần, boundary và trade-offs.
- [Technical Design](architecture/technical-design.md): chức năng ↔ công nghệ ↔ design pattern, trạng thái source/target và trust boundaries.
- [Agent Workflow](technical/agent-workflow.md): 7 roles, tools, contracts, loops và trạng thái.
- [Data Model & API](technical/data-model-and-api.md): baseline source khác target schema/route thế nào.
- [ADR index](architecture/decisions/README.md): quyết định và thay đổi theo thời gian.

## Quy tắc đồng bộ

SRS hiện hành là v4.0; root `SRS ATI.md` giữ làm lịch sử. Mermaid trong midterm phải trùng 5 hình chính trong System Design; không chỉnh hai bản độc lập. Timeline chi tiết theo Implementation Plan; roadmap/midterm chỉ tóm tắt.

| Nội dung cần cập nhật | Nguồn chuẩn | Tài liệu cần đồng bộ theo |
|---|---|---|
| Scope, FR/NFR và gate G0–G7 | SRS §3, §7–9 | Implementation Plan, Evaluation Plan, midterm |
| Vai trò và quy tắc điều phối | Agent Workflow + ADR-004 | HLD, System Design, SRS |
| Schema/API và chuyển trạng thái | Data Model & API | ERD/sequence, workflow, implementation tasks |
| Sơ đồ | System Design | 5 hình chính trong midterm |
| Lịch và phụ thuộc công việc | Implementation Plan | Roadmap, midterm, Team Task Guide |
| Kết quả chạy | Baseline Verification + evidence từng gate | Roadmap, midterm; không thay bằng mô tả target |

Nhật ký đồng bộ 08/10: thống nhất FR/NFR → P0–P7 → G0–G7; làm rõ Q&A budget, active run khi chờ, revision/version và delete/cleanup; tách ảnh minh họa khỏi biểu đồ thực nghiệm. Những cập nhật này là đặc tả/planning, chưa phải runtime evidence.

Source review 08/10 tại `ebb525a` không thay runtime evidence. Runtime log gần nhất thu 27/09 và tổng hợp 28/09. Thay đổi sau đó chỉ được đánh dấu Verified khi có lệnh/kết quả/ngày/người xác nhận. Không đưa secrets hoặc dữ liệu cá nhân vào repository.
