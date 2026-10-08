# ADR-005: Nhật ký thí nghiệm, kết quả âm và kiểm tái lập

**Trạng thái:** Chốt thiết kế 09/10/2026; implementation chưa nghiệm thu.<br>
**Bổ sung:** [ADR-004](ADR-004-multi-agent-research-delivery.md), không thay đổi phạm vi routine bản nộp.

## Bối cảnh

Manifest/metrics riêng lẻ không cho thấy các lần thử hỏng hoặc kết quả không cải thiện. Log vận hành cũng không thể thay một sổ nghiên cứu có giả thuyết, cấu hình và diễn giải. Nếu Writer chỉ đọc output cuối, bài báo dễ chọn lọc số đẹp hoặc gọi lỗi kỹ thuật là kết quả âm.

## Quyết định

1. Thêm `ExperimentJournalEntry` append-only theo `AnalysisRun`, riêng với `TaskEvent`/`AgentRun` và runner log. Ghi plan trước khi chạy, mỗi attempt, quan sát, diễn giải và kiểm tái lập; entry tham chiếu artifact/checksum/version. Correction là entry mới.
2. Lưu toàn bộ attempts, cả lỗi và `NO_IMPROVEMENT`. `NO_IMPROVEMENT` là phép chạy hợp lệ không vượt baseline theo metric đã chốt; `TECHNICAL_FAILURE` không phải kết quả nghiên cứu. Writer/Critic phải xét các attempt liên quan và hạn chế, không chọn một run thắng.
3. Phân biệt gói có manifest với lần kiểm lại thực tế. Chỉ gắn nhãn “ATI đã tái lập” sau một execution mới từ cùng manifest, so metric/chart data theo tolerance đã định, có entry `REPRODUCTION_CHECK`.
4. Bản nộp chỉ chạy routine allowlist. Mã do AI sinh là giai đoạn sau, chỉ mở khi có execution boundary cho mã không tin cậy và đánh giá an toàn/chất lượng/tái lập đủ mạnh; quyết định công nghệ sandbox bằng ADR sau.

## Hệ quả

Tăng schema, lưu trữ và thời gian một lần chạy lại. Đổi lại, Results có đường kiểm từ giả thuyết tới dữ liệu và giữ thất bại khoa học trung thực. Tính tái lập trên cùng seed là repeatability kỹ thuật; nghiên cứu có độ vững ngoài tập dữ liệu/seed cần đánh giá khác. Kết quả bên ngoài ATI luôn gắn nhãn chưa được ATI tái lập trừ khi ATI thật sự chạy lại method được hỗ trợ.

Chi tiết field/gate nằm tại [Experiment Journal](../../technical/experiment-journal-and-reproducibility.md) và [Evaluation Plan](../../project/evaluation-plan.md).
