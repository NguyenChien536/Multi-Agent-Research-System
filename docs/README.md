# Tài liệu Dự án ATI

Tài liệu dự án được version cùng mã nguồn để nhóm và người đánh giá cùng xem một nguồn thống nhất. Tài liệu phân biệt rõ kiến trúc/yêu cầu mục tiêu với tính năng đã có runtime evidence; sơ đồ target không phải bằng chứng implementation.

## Dành cho giảng viên / đánh giá

- [Báo cáo giữa kỳ](project/midterm-report.md): Overview, Problems/Objectives, Technical Approaches, System Design, Development Plan, Progress, AI Disclosure.
- [Đánh giá sản phẩm](project/product-assessment.md): định vị, giá trị cần kiểm chứng, release scope và claims không nên dùng.
- [Kiến trúc cấp cao (HLD)](architecture/system-architecture.md): boundary, container responsibilities, trade-offs, reliability và release gate.
- [AI Disclosure](project/ai-disclosure.md): con người chịu trách nhiệm, AI hỗ trợ, mục cần xác nhận.
- [SRS rút gọn](requirements/SRS.md): FR/NFR, acceptance, demo boundary và security gates.

## Dành cho thành viên nhóm

- [Roadmap, phân công, tiến độ](project/roadmap-and-progress.md): kỳ hạn 10/09–10/11, baseline evidence, việc còn lại.
- [Hướng dẫn task cho nhóm](project/team-task-guide.md): giải thích sản phẩm và giao việc cụ thể cho Vũ, Hiếu, My; không giao coding.
- [Baseline verification](project/baseline-verification.md): lệnh/kết quả runtime gần nhất; chưa phải nghiệm thu E2E.
- [ADRs](architecture/decisions/README.md): quyết định đã chốt và câu hỏi còn mở.

## Dành cho kỹ thuật

- [System Design](architecture/system-design.md): nguồn Mermaid chuẩn — C4 Container, Logical DFD, Inference Flow, Async Sequence, target ERD, Physical DFD và class diagram.
- [Agent Workflow](technical/agent-workflow.md): vai trò, loops, target routing và implementation gap.
- [Data Model & API](technical/data-model-and-api.md): source inventory, target schema/API và runtime evidence.
- [ADR-003](architecture/decisions/ADR-003-research-execution-modes.md): đa phương pháp, isolated execution, human study gate, durable wait/resume.

## Nguồn chuẩn và cập nhật

- `requirements/SRS.md` v3.0 là SRS hiện hành; `SRS ATI.md` v2.5 được giữ làm bản lịch sử đã superseded.
- `architecture/system-design.md` là nguồn chuẩn cho Mermaid diagrams; HLD ở `architecture/system-architecture.md` giải thích container, boundary và trade-offs.
- `project/baseline-verification.md` là nơi ghi lệnh/kết quả runtime gần nhất. Baseline hiện có được chạy ngày 27/09/2026 và tổng hợp ngày 28/09/2026; các thay đổi code sau mốc này chưa tự động được coi là đã xác minh.
- Khi cập nhật trạng thái, ghi ngày, command/evidence và người xác nhận. Không đưa secrets, khóa API hoặc dữ liệu cá nhân vào tài liệu hay repository.
