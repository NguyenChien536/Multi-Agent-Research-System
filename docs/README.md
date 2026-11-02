# Bắt đầu từ đây — Synthia

**Synthia — Multi-Agent Research System** hỗ trợ người nghiên cứu đi từ câu hỏi/tài liệu đến bản thảo bài báo có nguồn, có kết quả thực nghiệm khi phương pháp yêu cầu. Đây là đề tài học phần ATI; bản thảo vẫn cần người nghiên cứu kiểm tra.

**Cập nhật 02/11/2026:** nền `develop@bb63c99` / PR #78 có **425 backend tests, 20 frontend tests và 5/5 CI đạt**; đã có gói tái lập thực nghiệm theo phiên bản. Đang triển khai **P7 / issue #79 — nền đóng băng protocol, thu output và chấm so sánh**. Chưa có kết quả benchmark khoa học hoặc kết luận multi-agent tốt hơn single-agent. **Chưa sẵn sàng production.**

## Chỉ cần mở ba tài liệu thường xuyên

| Bạn muốn biết | Mở |
|---|---|
| Tiếp theo phải làm gì, đến production ra sao? | [Kế hoạch triển khai](project/implementation-plan.md) — thứ tự, lịch ước lượng, acceptance và release gates |
| Đang làm đến đâu, phần nào đã kiểm chứng? | [Roadmap và tiến độ](project/roadmap-and-progress.md) — có code / đã kiểm / còn thiếu |
| Kiến trúc, dữ liệu và luồng chạy như thế nào? | [System Design](architecture/system-design.md) — thiết kế mục tiêu để triển khai/vẽ sơ đồ |

## Việc ngay tiếp theo

1. **P7 / #79**: hoàn tất kiểm nền evaluation CLI; [Evaluation Plan §7](project/evaluation-plan.md#7-công-cụ-chuẩn-bị-và-chấm-đánh-giá--issue-79) ghi lệnh, schema và giới hạn. Smoke fixture không phải kết quả đánh giá thật.
2. Chuẩn bị câu hỏi/nguồn thật, nối adapter chạy A/B/C với workflow/model/nguồn đã kiểm soát; chạy pilot trước held-out, giữ cả lỗi và kết quả không thuận lợi.
3. Khép các kiểm tra browser/runtime, restart/concurrency và ba luồng trước staging → dùng thử giới hạn → production. **10/11 là mốc nộp/demo, chưa phải cam kết production.**

Quy trình Git: issue nhỏ → branch chức năng/sửa lỗi → tests/review → PR develop. Chỉ đưa lên main khi CI và demo end-to-end trên đúng candidate đạt. Xem [CONTRIBUTING](../CONTRIBUTING.md).

## Người dùng nhận được gì?

| Loại nghiên cứu | Kết quả |
|---|---|
| Tổng quan tài liệu | Bản thảo có nguồn/bằng chứng, gợi ý research gap và giới hạn |
| Thực nghiệm tính toán | Bản thảo với số liệu/biểu đồ thật, journal và thông tin chạy lại cho routine được hỗ trợ |
| Lab/khảo sát/thực địa | Protocol lúc chờ; bản thảo thực nghiệm sau khi tải đủ kết quả có nguồn gốc |
| Nhiều bài | A/B/C có thể chờ, D vẫn làm tiếp; các bài có trạng thái/dữ liệu riêng |

Đây là phạm vi mục tiêu. Roadmap nêu chính xác phần nào chưa đạt; không coi tất cả dòng trên là đã nghiệm thu.

## Tài liệu tra cứu khi cần

| Nội dung | Nguồn chuẩn |
|---|---|
| Yêu cầu/FR/NFR và G0–G7 | [SRS](requirements/SRS.md); bản đồng bộ thuận tiện mở/nộp: [SRS ATI.md](../SRS%20ATI.md) |
| Luồng người dùng/đầu ra | [User Journey](project/user-journey-and-outputs.md) |
| Báo cáo học phần | [Midterm report](project/midterm-report.md) |
| Lệnh/kết quả audit, lỗi tái hiện, evidence lịch sử | [Baseline Verification](project/baseline-verification.md#kiem-tra-2026-10-22) |
| Cách đo giá trị đa tác tử | [Evaluation Plan](project/evaluation-plan.md) |
| Journal, kết quả âm, tái lập | [Experiment Journal](technical/experiment-journal-and-reproducibility.md) |
| Lý do chọn kiến trúc | [HLD](architecture/system-architecture.md), [Technical Design](architecture/technical-design.md), [ADR](architecture/decisions/README.md) |
| Contract dữ liệu/agents | [Data Model & API](technical/data-model-and-api.md), [Agent Workflow](technical/agent-workflow.md) |

Không cần đọc mọi file theo thứ tự. Plan giữ việc **sẽ làm**, Roadmap giữ việc **đã có bằng chứng**; biên bản giữ chi tiết kiểm tra. Không tạo thêm tài liệu trạng thái trùng nhau.

## Từ ngữ ngắn gọn

- **Issue:** một việc cụ thể với điều kiện để biết khi nào xong.
- **PR:** đề nghị nhập thay đổi, có diff và kết quả kiểm tra.
- **CI:** các kiểm tra tự động trên GitHub.
- **Gate:** cổng nghiệm thu; chưa đạt thì chưa gọi chặng đó hoàn thành.
- **Staging:** môi trường giống production dùng để thử trước phát hành.
- **Production:** môi trường phục vụ người dùng thật, có giám sát, backup và khả năng phục hồi.
