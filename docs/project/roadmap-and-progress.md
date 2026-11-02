# Tiến độ triển khai — Synthia

**Cập nhật: 02/11/2026.** Code đã kiểm e457f17 / PR #82; bộ chạy P7 đã qua CI, tiếp theo pilot issue #83. Hạn cuối kỳ mới: 05/11/2026; mục tiêu chốt bản nộp trước hết 04/11.

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
| Xuất bản thảo | Markdown và ZIP nguồn IEEE/ACM kèm hình/dữ liệu biểu đồ/provenance theo version | PR #64; đã biên dịch và xem PDF mẫu. Chưa có dịch vụ tự biên dịch PDF trong backend; gói tái lập thực nghiệm đã có ở PR #78, xem bằng chứng bên dưới |

**Chưa đủ điều kiện phát hành production hoặc nâng `main` thành bản demo đã nghiệm thu.** Các chức năng có code và tests không tự đóng toàn bộ G0–G7.

**Cập nhật #84 / PR #85:** code c72e936 với contract v4/hierarchy theo loại bài đạt 118 focused tests, 513 backend tests, 20 frontend tests và 5/5 CI; chưa chấm bài thật sau thay đổi. Writer của bài được audit nhận 5 evidence records từ 3 nguồn; giới hạn chính ở lượng bằng chứng và tổ chức nội dung, chưa có bằng chứng context overflow. Xem Agent Workflow §9.1–9.2.

## Bằng chứng cập nhật 02/11

- **P6 / PR #78 đã merge tại `bb63c99`:** 425 backend tests, 20 frontend tests và 5/5 CI đạt. Export theo owner/version, đóng băng input/code/result, kiểm hash, giữ kết quả âm, journal cutoff; chạy ZIP độc lập thực sự, không dùng LLM để giả kết quả tính toán.
- **P7 / #79 đã merge qua PR #80:** freeze/record/blind/score/summarize; 458 backend tests, 20 frontend tests, 5/5 CI đạt. Giữ attempt đầu, reruns, missing/failures, delta âm và split riêng; chưa có kết quả khoa học.
- **P7 / #81, PR #82 đã qua kiểm thử:** A controller và B/C production graph chạy trên frozen lexical corpus với model/cap chung; scope riêng cho DB/providers, ledger tổng bền vững, timeout/failure/rerun và draft chưa đạt được giữ. Code e457f17 đạt 485 backend tests, 20 frontend tests, 60 ca focused và 5/5 CI; CLI plan trong Docker có 0 provider calls. Issue #83 dành cho pilot thật. Không dùng các fixture này như bằng chứng chất lượng nghiên cứu.
- **Chưa có benchmark thật:** chưa chốt/chạy model trả phí trên pilot/held-out và chưa chấm output thật. Chọn profile/ngân sách, freeze code/corpus rồi chạy có giới hạn; G7, browser/runtime/fault và P8–P10 chưa đóng.

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
| 1 | #86: nguồn/bằng chứng đủ các khái niệm; tích hợp và nghiệm thu FE/API trên cùng candidate | Bài có lập luận và nguồn liên quan, luồng người dùng chạy thật | Chấm bài đa chủ đề/loại; không lấy đủ query hoặc số ref làm bằng chứng chất lượng |
| 2 | P7: đánh giá theo Evaluation Plan | Biết chất lượng, nguồn hỗ trợ, chi phí, thời gian và giá trị multi-agent trên bộ câu hỏi cố định | Baseline/ablation cùng model/corpus/cap; giữ cả lỗi/kết quả âm và giới hạn mẫu |
| 3 | Nghiệm thu runtime/UI còn thiếu | Ba luồng REVIEW, tính toán, human-led hoạt động sau lỗi/khôi phục | Browser + broker + restart/concurrency/fault tests; không đóng gate chỉ từ mock tests |
| 4 | P8 → P9 → P10 | Staging, backup/restore, monitoring vận hành, pilot rồi phát hành giới hạn | Cùng image digest, rollback, cảnh báo thật, tải/chi phí đã đo và quyết định go/no-go |

Sửa dữ liệu/phương pháp thực nghiệm là **lượt nghiên cứu mới**, không đi qua editorial revision để tái dùng Results cũ. Bản thực nghiệm lịch sử không có đủ snapshot phải báo rõ chưa thể sửa theo luồng này. Không tự tăng ngân sách để làm lại một yêu cầu thất bại.
