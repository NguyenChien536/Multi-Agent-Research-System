# Luồng sử dụng và đầu ra bài báo — ATI

**Quyết định thiết kế:** 09/10/2026. Đây là contract mục tiêu; [SRS v4.1](../requirements/SRS.md) quy định nghiệm thu, [System Design](../architecture/system-design.md) là nguồn chuẩn của sơ đồ. Chưa khẳng định các luồng đã chạy.

## 1. ATI giải quyết việc gì?

Người nghiên cứu thường phải tự gom nguồn, đối chiếu claim, chọn phương pháp, theo dõi thí nghiệm, viết và rà lại bài. ATI hỗ trợ chuỗi công việc đó trong **một workspace cho mỗi bài**. Giá trị đa tác tử nằm ở các handoff có thể kiểm: Researcher tìm cả nguồn trái chiều; Evidence Analyst neo claim vào đoạn nguồn; Methodologist nêu phương pháp và dữ liệu cần; Data Analyst chỉ diễn giải kết quả tính toán thật; Writer viết bài; Critic trả lỗi theo section/claim; Supervisor điều phối. Router, budget guard, validator và runner là code, không tính là agent.

Mục tiêu cuối của mỗi bài là **bản thảo bài báo hoàn chỉnh về cấu trúc và có căn cứ**. ATI không bảo đảm tính mới, tính đúng của toàn bộ lập luận hay khả năng đăng tạp chí. Người dùng quyết định câu hỏi, quyền tự động, nguồn được nạp, phương pháp và chấp nhận bản cuối.

## 2. Người dùng thao tác thế nào?

| Bước nhìn thấy trên UI | Người dùng làm | ATI tự làm | Dữ liệu lưu bền vững |
|---|---|---|---|
| Danh sách bài | Tạo hoặc mở một bài; nhập câu hỏi, tùy chọn PDF/CSV | Tạo task có owner, đề xuất loại bài và plan | Task, input metadata, plan version |
| Lập kế hoạch | Chọn automatic hoặc duyệt/sửa plan ở assisted; chỉ cần thêm quyết định khi policy yêu cầu | Phân scope, phương pháp, budget và công cụ | Decision, plan version, event |
| Nghiên cứu | Xem tiến độ, có thể rời trang | Tìm/ingest nguồn, đối chiếu evidence, tìm bổ sung theo Critic trong giới hạn | Sources, chunks, claims, evidence, run/checkpoint/events |
| Thực nghiệm | Nếu tính toán: nạp CSV hợp lệ. Nếu ngoài hệ thống: tải protocol/biểu mẫu, thực hiện nghiên cứu và sau đó nạp data/kết quả thật | Phân tích CSV bằng routine được hỗ trợ; hoặc dừng bền vững ở WAITING_USER_DATA | File private + checksum, manifest/kết quả hoặc protocol/checkpoint |
| Hoàn thiện | Đọc, hỏi, yêu cầu sửa hoặc xuất bài | Writer/Critic/Validator hoàn thiện bài, lưu version, trả citations và artifacts | Report versions, validation, timeline, export |

Dashboard mỗi bài hiển thị `status`, `stage`, vai trò đang làm, nguồn/budget, lần cập nhật gần nhất, bản thảo mới nhất và **việc cần người dùng làm**. Trạng thái chờ không bị hiển thị là đang “AI suy nghĩ”. Có thể chuyển sang bài khác ngay.

## 3. Ba đường tới bài báo hoàn chỉnh

| Đường | Khi nào đủ để hoàn thành | Bài báo nhận được | Artifact kèm theo |
|---|---|---|---|
| REVIEW | Corpus/search scope được ghi; claims/citations và cấu trúc qua gate | Review article: Title, Abstract, Introduction, search/scope, synthesis, Discussion/gap, Limitations, Conclusion, References | Source/evidence log, claim links, Markdown; không tự gọi systematic review/PRISMA |
| EMPIRICAL_COMPUTATIONAL | Input hợp lệ; method/spec được cố định trước run; routine thực sự thành công; metrics/charts/manifest qua gate | Empirical paper: Title, Abstract, Introduction/Related work, RQ/hypothesis, Methods, Results, Discussion, Limitations, Conclusion, References | CSV/config hash, seed, routine/version, metrics, charts, manifest/README tái lập |
| EMPIRICAL_HUMAN | Người dùng nạp data/kết quả thật và metadata phương pháp đủ để mô tả, kiểm provenance và viết Results có căn cứ | Empirical paper cùng các phần trên, ghi rõ ATI đã phân tích lại phần nào và phần nào là kết quả do người dùng cung cấp | Reviewed protocol/biểu mẫu, file được phép, nguồn gốc kết quả, giới hạn xác minh |

Với nghiên cứu cần lab, tuyển người, khảo sát hoặc phê duyệt đạo đức: ATI chỉ **gợi ý protocol/checklist và nội dung cần thu thập**, con người thực hiện các bước ngoài hệ thống. Protocol đã review là đầu ra trung gian tải được khi chờ; **không đánh dấu task `COMPLETED` và không viết Results giả**. Nếu người dùng không có kết quả, task tiếp tục WAITING_USER_DATA, hoặc họ chủ động hủy/lưu trữ bản nháp. Không âm thầm đổi thành review/proposal. Nếu thiếu metadata quan trọng (mẫu, phương pháp, đơn vị đo, thời điểm, xử lý dữ liệu), ATI yêu cầu bổ sung trước khi hoàn thành.

## 4. Hai bài song song và cách lưu

Ví dụ: bài A về khảo sát đang WAITING_USER_DATA. ATI đã lưu plan, nguồn, protocol, checkpoint, budget/counters và timeline của A trong PostgreSQL; PDF/CSV/protocol trong private ArtifactStore. Celery job của A đã kết thúc. Người dùng tạo bài B về tổng quan tài liệu, B có ID, run và tài nguyên riêng; có thể hoàn thành B trước A. Vài tuần sau người dùng mở A từ dashboard, nạp dữ liệu, ATI kiểm owner/file READY/plan version/checkpoint rồi đưa **chính run A** vào QUEUED để tiếp tục. Không khởi chạy lại nghiên cứu từ đầu và không trộn nguồn hoặc file của B.

Một task chỉ có một run chưa kết thúc; user có nhiều task. Mặc định tối đa 2 job RUNNING/user. QUEUED và WAITING_* không chiếm suất; nếu 2 job khác đang chạy, resume A vẫn được ghi bền vững trong outbox và đợi công bằng. Quota số workspace và dung lượng lưu trữ là cấu hình riêng. Các thao tác trùng key trả cùng kết quả; upload/decision cũ hoặc task đã xóa không resume được. Chờ nhiều ngày không tiêu active-time budget, nhưng số call/cost đã dùng không được reset.

## 5. Thực nghiệm tính toán không bị mập mờ

1. Methodologist chốt RQ/hypothesis, dataset schema, target/features, metric, split/seed và routine trước khi xem kết quả; ATI ghi `PLAN_FROZEN` trong nhật ký thí nghiệm. Bản nộp hỗ trợ `tabular_regression_v1` trên numeric CSV, không giả vờ hỗ trợ mọi lĩnh vực.
2. Preflight kiểm owner/file READY, số hàng/cột, đơn vị/metadata cần thiết, missing values, leakage, target và routine compatibility. Input không đạt thì UI nêu lỗi và yêu cầu sửa, task chưa hoàn thành.
3. Worker gửi immutable manifest (input checksum, config, seed, routine/code/container version) cho launcher; runner riêng chạy routine với giới hạn tài nguyên, không nhận code do LLM sinh. Retry kỹ thuật giữ cùng manifest/idempotency key; không lựa chọn lần chạy đẹp nhất.
4. Validator kiểm exit status, JSON schema, finite metrics, chart paths/checksums và input/config lineage; mọi attempt được ghi riêng. ATI chạy lại từ cùng manifest trong runner mới và ghi kết quả đối chiếu. Data Analyst diễn giải **kết quả thực**, kể cả `NO_IMPROVEMENT`; Writer đưa vào Methods/Results/Discussion; Critic kiểm overclaim và việc bỏ qua run bất lợi.
5. Lỗi/timeout sau retry → NEEDS_REVIEW hoặc đợi người dùng sửa input; không sinh Results và không được gọi là “kết quả âm”. Đổi input/method/metric tạo plan/analysis version mới, vô hiệu hóa kết quả cũ. Bản cũ còn để audit nhưng không được dùng làm kết quả của bản mới. Người dùng xem timeline experiment và tải journal/manifest cùng gói tái lập.

Dữ liệu human-led có hai mức: (a) CSV/số liệu trong routine ATI hỗ trợ thì ATI phân tích lại và ghi AnalysisRun; (b) kết quả đã phân tích ở ngoài thì ATI kiểm file, phương pháp, đơn vị, nguồn gốc và consistency ở mức khả thi, gắn nhãn **user-supplied, chưa được ATI tái lập**. Không dùng RAG để tính số liệu; không suy ra chất lượng thí nghiệm chỉ từ file upload.

## 6. Khi nào được hiện chữ “Hoàn thành”?

`COMPLETED` cần đúng loại bài đã chọn, đủ sections bắt buộc, không có Results chưa quan sát, citations và analysis lineage hợp lệ, không có lỗi blocking từ Critic/Validator. `PARTIAL` là bản nháp có các phần hợp lệ nhưng thiếu nội dung được nêu rõ; `NEEDS_REVIEW` có lỗi chưa giải quyết; cả hai không được gắn nhãn bài báo hoàn chỉnh. Sau hoàn thành, hỏi đáp đọc report version và evidence; sửa bài tạo version mới, không ghi đè bản trước.

Chất lượng lập luận, chuẩn ngành/tạp chí, đạo đức, tính mới và kiểm chứng kết quả người dùng cung cấp vẫn cần người nghiên cứu hoặc chuyên gia xác nhận. Kế hoạch [đánh giá multi-agent](evaluation-plan.md) so sánh cùng corpus/model/budget với single-agent và ablation, báo cả chất lượng lẫn chi phí để kiểm tra giá trị phân vai thực tế.
