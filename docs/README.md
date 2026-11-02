# Bắt đầu từ đây — Synthia

**Synthia — Multi-Agent Research System** hỗ trợ người nghiên cứu đi từ câu hỏi/tài liệu đến bản thảo bài báo có nguồn, có kết quả thực nghiệm khi phương pháp yêu cầu. Đây là đề tài học phần ATI; bản thảo vẫn cần người nghiên cứu kiểm tra.

**Cập nhật 02/11/2026 — P7 / #81, PR #82:** bộ chạy A/B/C dùng cùng nguồn/model/cap đã qua **485 backend tests, 20 frontend tests và 5/5 CI** trên code `e457f17`; thêm 60 ca focused evaluation đạt. Issue **#83** tiếp tục pilot thật có ngân sách và chấm output. Chưa có kết quả benchmark khoa học hoặc kết luận multi-agent tốt hơn single-agent. **Chưa sẵn sàng production.**

## Chỉ cần mở ba tài liệu thường xuyên

| Bạn muốn biết | Mở |
|---|---|
| Tiếp theo phải làm gì, đến production ra sao? | [Kế hoạch triển khai](project/implementation-plan.md) — thứ tự, lịch ước lượng, acceptance và release gates |
| Đang làm đến đâu, phần nào đã kiểm chứng? | [Roadmap và tiến độ](project/roadmap-and-progress.md) — có code / đã kiểm / còn thiếu |
| Kiến trúc, dữ liệu và luồng chạy như thế nào? | [System Design](architecture/system-design.md) — thiết kế mục tiêu để triển khai/vẽ sơ đồ |

**Mốc cuối kỳ mới:** chốt bản nộp trước hết 04/11, bàn giao/dự phòng 05/11 theo yêu cầu 3 ngày. Đang nghiệm thu #84 về bố cục/lập luận từng loại bài; output thật vẫn cần đọc và chấm.

## Việc ngay tiếp theo

1. **P7 / #83**: chốt profile/ngân sách và chạy pilot thật; [Evaluation Plan](project/evaluation-plan.md) §7–8 ghi cách thực thi và chấm. Bộ chạy #81 đã kiểm thử; smoke fixture không phải kết quả đánh giá thật.
2. Chốt model/giá trần/ngân sách tổng và corpus; freeze source sạch đúng commit, chạy pilot có giới hạn trước held-out, giữ cả lỗi và kết quả không thuận lợi.
3. Khép các kiểm tra browser/runtime, restart/concurrency và ba luồng trước staging → dùng thử giới hạn → production. **05/11 là hạn cuối kỳ mới; bản nộp phải chốt trước hết 04/11. Production có các gate riêng.**

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
