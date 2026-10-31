# Tiến độ triển khai — Synthia

**Cập nhật: 31/10/2026.** Nền develop@f252223 / PR #76; đang khép P6 với issue #77. Hạn demo: 10/11/2026.

Tài liệu này trả lời **đã có gì, đã kiểm đến đâu, tiếp theo làm gì**. Thứ tự và điều kiện phát hành nằm trong [Implementation Plan](implementation-plan.md). Các biên bản ngày 22–24/10 là lịch sử, không phải trạng thái code hiện tại.

## 1. Hiện tại người dùng làm được gì?

| Chức năng | Đã triển khai | Bằng chứng và giới hạn |
|---|---|---|
| Tài khoản và nhiều bài độc lập | Đăng nhập, quyền owner, danh sách bài, quota chạy, hủy và xóa có cleanup nền | Kiểm thử API/lifecycle. Chưa nghiệm thu toàn bộ tải, lỗi hạ tầng và browser cho mọi chế độ |
| Bài tổng quan có nguồn | Tìm/fetch nguồn, upload PDF và ingestion nền, evidence/claims, Writer/Critic/validator | Có lượt REVIEW chạy provider thật. Không tự nhận systematic review/PRISMA hay chất lượng học thuật chỉ vì workflow hoàn tất |
| Cấu trúc bài theo loại nghiên cứu | Khung riêng REVIEW / thực nghiệm tính toán / dữ liệu thực địa; Related Work, câu hỏi/gap/đóng góp, văn xuôi, kiểm tra kết luận và hình | PR #62/#64; giới hạn phương pháp và bộ kiểm tra heuristic được công khai. Provider thật mới xác minh cho REVIEW trong các lượt gần đây |
| Chờ duyệt và chờ dữ liệu | Checkpoint PostgreSQL, duyệt theo plan version, WAITING không giữ worker, resume theo quyết định | API/graph tests có khôi phục state; chưa coi đó là đầy đủ bằng chứng kill/restart process hay nhiều worker cạnh tranh |
| Thực nghiệm được hỗ trợ | Routine regression có baseline, manifest, kết quả âm/lỗi, kiểm tra lặp và nhật ký | Có kiểm thử routine và execution riêng. Chưa mở chạy code tùy ý; chưa nghiệm thu production sandbox |
| Theo dõi tiến độ | Tổng quan nhiều bài, trạng thái/stage, lịch sử agent, ngân sách và cảnh báo từ dữ liệu đã lưu | PR #57. Dashboard vận hành, cảnh báo thực sự gửi được và tải staging còn ở P8–P10 |
| Hỏi bài đã viết | Hỏi đáp dựa trên phiên bản bài và nguồn/chunk của phiên bản đó; lịch sử và chống gửi lặp | PR #58. Câu trả lời vẫn cần người dùng đối chiếu bằng chứng |
| Sửa cách trình bày bài | Issue #65: chọn phiên bản, gửi yêu cầu, Writer/Critic/validator tạo bản mới; nguồn và dữ liệu đóng băng theo bản gốc | Kiểm thử quyền, cạnh tranh, stale base, budget, hủy/xóa và mô phỏng crash/redelivery. Một lượt provider thật tạo v3 từ v2, v2 giữ nguyên |
| Xuất bản thảo | Markdown và ZIP nguồn IEEE/ACM kèm hình/dữ liệu biểu đồ/provenance theo version | PR #64; đã biên dịch và xem PDF mẫu. Chưa có dịch vụ tự biên dịch PDF trong backend; gói chạy lại thực nghiệm đầy đủ còn cần hoàn thiện |

**Chưa đủ điều kiện phát hành production hoặc nâng `main` thành bản demo đã nghiệm thu.** Các chức năng có code và tests không tự đóng toàn bộ G0–G7.

## Bằng chứng cập nhật 31/10

- Nền `develop@f252223`: PR #66/#68 (sửa bài và citation theo phiên bản), #70 (viết học thuật), #72 (nguồn học thuật/provenance), #74/#76 (kiểm hỗ trợ và cân bằng truy vấn) đã merge; **413 backend tests, 5/5 CI đạt** trên PR #76. Pilot Gemini thật phân biệt được phát biểu có điều kiện với kết luận hybrid vượt bằng chứng; chưa phải semantic benchmark.
- Issue #77 bổ sung gói thí nghiệm theo version: input/code/environment đóng băng trước chạy, kết quả đầy đủ, journal theo mốc version, checksum, launcher độc lập và SVG đo từ chart data. Bài cũ thiếu snapshot báo rõ, không dùng code/data mới để lấp chỗ trống. Xem kiểm thử và CI của PR liên kết issue #77 để biết trạng thái nghiệm thu cuối cùng.
- Lượt kiểm tập trung ban đầu: **38 tests backend liên quan đạt**; chạy thật routine và chạy lại ZIP bằng Python độc lập, giữ kết quả âm, kiểm sai quyền/tamper/missing snapshots/version isolation. **20 frontend tests và TypeScript đạt** cục bộ; toàn bộ backend trên DB PostgreSQL mới đạt **425 tests**. CI của candidate mới phải đạt trước merge. Đây chưa phải browser E2E hay nghiệm thu production.

## 2. Bằng chứng của lượt bàn giao #65

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Toàn bộ backend trên DB PostgreSQL/pgvector mới, migrate từ rỗng | **343 tests đạt** | Provider được thay bằng fixture xác định trong suite; không dùng DB dev để chạy pytest |
| Các ca riêng cho sửa bài | **15 tests đạt** | Bao gồm checkpoint PostgreSQL, rollback khi publication lỗi và mô phỏng ngắt sau checkpoint; chưa thay cho kill/restart Celery process thực |
| Frontend | **17 tests đạt**, gồm hồi quy nhãn trích dẫn ở trang sửa bài; production build và Docker image build đạt | Phần giao diện/ngôn ngữ đang chỉnh độc lập không tự được coi là đã phát hành |
| Provider thật: chỉnh bản thảo REVIEW | Task `f0142565-3e21-46b3-adc4-d51ee21a29a8`: v2 → v3, **PASSED nội bộ**, 1.172 từ | Hash nội dung v2 giữ nguyên; nguồn bản mới thuộc v2; lượt sửa chỉ có Writer/Critic/PostProcessor. Đây là smoke nhỏ, không đo ưu thế khoa học |
| Export sau sửa | Đọc lại version mới và tải publication ZIP có xác thực thành công | Không chứng nhận chấp nhận xuất bản hoặc đủ yêu cầu của mọi venue |

CI của PR là cổng trước merge; release `main` vẫn cần demo UI/API/broker/provider thật trên cùng candidate theo CONTRIBUTING. Không lấy tỷ lệ COMPLETED trong DB dev chứa dữ liệu thử lịch sử làm thước đo chất lượng.

## 3. Thứ tự tiếp theo

| Ưu tiên | Việc cần hoàn thiện | Người dùng nhận được gì? | Điều kiện nghiệm thu |
|---|---|---|---|
| 1 | Nghiệm thu P6 / #77: gói bàn giao/tái lập thực nghiệm theo version | Tải đúng input được phép, config, routine/launcher, metrics, biểu đồ, manifest và journal của lần chạy | Đúng owner/version/hash; không trộn artifacts của lần mới hơn; không xuất kết quả chạy thất bại như thành công |
| 2 | P7: đánh giá theo Evaluation Plan | Biết chất lượng, nguồn hỗ trợ, chi phí, thời gian và giá trị multi-agent trên bộ câu hỏi cố định | Baseline/ablation cùng model/corpus/cap; giữ cả lỗi/kết quả âm và giới hạn mẫu |
| 3 | Nghiệm thu runtime/UI còn thiếu | Ba luồng REVIEW, tính toán, human-led hoạt động sau lỗi/khôi phục | Browser + broker + restart/concurrency/fault tests; không đóng gate chỉ từ mock tests |
| 4 | P8 → P9 → P10 | Staging, backup/restore, monitoring vận hành, pilot rồi phát hành giới hạn | Cùng image digest, rollback, cảnh báo thật, tải/chi phí đã đo và quyết định go/no-go |

Sửa dữ liệu/phương pháp thực nghiệm là **lượt nghiên cứu mới**, không đi qua editorial revision để tái dùng Results cũ. Bản thực nghiệm lịch sử không có đủ snapshot phải báo rõ chưa thể sửa theo luồng này. Không tự tăng ngân sách để làm lại một yêu cầu thất bại.
