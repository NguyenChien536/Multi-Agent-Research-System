# Đặc tả Yêu cầu Rút gọn — ATI

> **Phiên bản định hướng:** 3.0 · **Cập nhật:** 06/10/2026
> Bản này chốt phạm vi sản phẩm mục tiêu và tiêu chí nghiệm thu. Phần trạng thái hiện tại chỉ ghi theo bằng chứng baseline ngày 27/09/2026; các yêu cầu target chưa được xem là đã triển khai. SRS ATI.md là bản 2.5 lưu trữ đã superseded; bản yêu cầu hiện hành nằm trong tài liệu này. Sơ đồ chuẩn: [System Design](../architecture/system-design.md).

## 1. Mục đích, vấn đề và phạm vi

ATI là hệ thống điều phối nghiên cứu có AI hỗ trợ, giúp cá nhân/người học chuyển từ câu hỏi nghiên cứu sang một trong các đầu ra phù hợp: tổng quan tài liệu, candidate research question/gap, giả thuyết/hướng nghiên cứu, protocol, phân tích dữ liệu được hỗ trợ và bản thảo bài báo theo loại nghiên cứu.

Hệ thống tiếp nhận nguồn web và tài liệu người dùng cung cấp. Với nghiên cứu tính toán, ATI chỉ chạy phân tích thuộc danh mục routine an toàn, có cấu hình và dữ liệu đầu vào được kiểm tra. Với nghiên cứu cần lab, khảo sát, thực địa hoặc người tham gia, ATI tạo protocol và hướng dẫn; nhà nghiên cứu tự xin review cần thiết, tự thực hiện và nạp kết quả đã được phép xử lý. ATI không tuyển người hoặc thực hiện nghiên cứu ngoài đời.

**Vấn đề cần giải quyết:** tìm kiếm và tổng hợp nguồn tốn công; câu trả lời LLM khó kiểm chứng; thiếu kết nối giữa claim, bằng chứng, dữ liệu/phương pháp và kết quả; quy trình nghiên cứu nhiều bước cần lưu tiến độ lâu dài; một báo cáo thực nghiệm phải dựa trên dữ liệu thật chứ không được tự bịa kết quả.

**Ngoài cam kết demo trước 10/11/2026:** hỗ trợ đầy đủ mọi lĩnh vực/chuẩn báo cáo, runner cho mã tùy ý, thực hiện lab/thực địa, tuyển người, xử lý dữ liệu định danh nhạy cảm, collaboration/tenant doanh nghiệp, DOCX và image enrichment hoàn chỉnh. Một demo có thể triển khai sâu một đường nghiên cứu và trình bày các đường khác ở mức protocol/target; không tuyên bố hỗ trợ mọi phương pháp.

## 2. Người dùng và vai trò

| Tác nhân | Quyền/trách nhiệm |
|---|---|
| Researcher/User | Tạo task, chọn loại nghiên cứu/đầu ra, tải nguồn/dữ liệu được phép, duyệt kế hoạch khi cấu hình yêu cầu, cung cấp quyết định hoặc kết quả bên ngoài, kiểm tra bài và nguồn |
| ATI workflow | Điều phối có giới hạn; tìm và xử lý nguồn; đề xuất phương pháp; gọi provider; lưu trạng thái, provenance và artefact |
| Reviewer/Instructor (ngoài hệ thống hoặc user được mời sau này) | Con người đánh giá protocol/ethics hoặc nội dung khoa học; Critic agent không thay thế vai trò này |
| Search / LLM providers | Dịch vụ ngoài; nội dung gửi đi, chi phí và lỗi phải có cấu hình/ghi nhận phù hợp |

## 3. Yêu cầu chức năng mục tiêu

| ID | Yêu cầu | Tiêu chí nghiệm thu mục tiêu |
|---|---|---|
| FR-01 | Quản lý task và quyền sở hữu | User tạo/xem task của mình; mọi API kiểm tra owner; kiểm thử truy cập chéo user bị từ chối |
| FR-02 | Nhập nguồn | Hỗ trợ nguồn web và tải lên tài liệu nghiên cứu; xác thực định dạng/kích thước, checksum, owner, trạng thái xử lý và lỗi; không biến file tải lên thành nội dung đáng tin mặc định |
| FR-03 | Kế hoạch và phê duyệt | Supervisor đề xuất câu hỏi, phạm vi, loại nghiên cứu, phương pháp, nguồn, budget và đầu ra; lưu version/checkpoint; user có thể duyệt/sửa/hủy khi chế độ yêu cầu |
| FR-04 | Tổng hợp nguồn và candidate gap | Duy trì provenance source → chunk → evidence → claim; nêu phạm vi tìm kiếm, thiếu sót, mâu thuẫn; gọi gap là candidate, không khẳng định bao quát toàn ngành |
| FR-05 | Bounded research loop | Critic có thể yêu cầu evidence còn thiếu; macro loop tối đa 3 vòng và dừng nếu không thêm nguồn/evidence sau dedup; ghi verdict và lý do |
| FR-06 | Thiết kế phương pháp | Đề xuất giả thuyết/câu hỏi, thiết kế và protocol theo loại nghiên cứu; phân biệt hướng dẫn mẫu với phê duyệt đạo đức/chuyên môn |
| FR-07 | Chạy phân tích được hỗ trợ | Chỉ chạy routine đã cho phép trên dữ liệu đã kiểm tra trong runner cô lập; lưu routine/version, config, input/output artifact, lỗi và giới hạn tài nguyên; không chạy LLM-generated arbitrary code |
| FR-08 | Nghiên cứu ngoài hệ thống | Với lab/khảo sát/thực địa/người tham gia, chỉ xuất protocol/checklist; task chuyển WAITING_USER_DATA; sau khi user nạp kết quả được phép, tạo job resume; không tự tuyển/thu thập dữ liệu |
| FR-09 | Bài báo theo loại | Sinh cấu trúc đúng với loại đầu ra được hỗ trợ; empirical Results chỉ có khi có dữ liệu thật; thiếu data thì xuất review/protocol hoặc phần chưa hoàn tất có nhãn |
| FR-10 | Critic và sửa | Critic kiểm tra evidence, tính nhất quán phương pháp, phạm vi và phần thiếu; Writer sửa có giới hạn; không mô tả Critic như peer reviewer độc lập |
| FR-11 | Citation và lineage | Validator xác nhận citation trỏ đúng report/task/source/chunk; claim dựa trên kết quả tính toán truy xuất qua evidence → output artifact → AnalysisRun/input/routine; tách referential integrity khỏi đánh giá claim có được evidence hỗ trợ hay không |
| FR-12 | Theo dõi task | UI hiển thị stage, status, lần lặp, điểm đang chờ user, cảnh báo và lỗi; có polling hoặc SSE theo trạng thái triển khai; log có correlation/task ID, thời gian và provider usage đã redacted |
| FR-13 | Export | Tạo Markdown trước; PDF sau khi renderer và quyền tải đã xác minh; xuất report/protocol/artifacts với trạng thái hoàn chỉnh/partial rõ |
| FR-14 | Ảnh minh họa tùy chọn | Ưu tiên ảnh từ trang đã thu thập; provider ảnh chỉ là fallback có cấu hình/quota; giữ attribution/license status; user bỏ từng ảnh/tắt tất cả; ảnh không phải evidence |

FR-07 và FR-08 là hai nhánh của quyết định phương pháp: ATI chạy routine tính toán được hỗ trợ trong phạm vi kiểm soát, hoặc dừng ở protocol để con người thực hiện nghiên cứu ngoài hệ thống rồi nạp dữ liệu/kết quả được phép. Cả hai nhánh đều phải duy trì provenance và không được tạo Results khi thiếu dữ liệu thật.

## 4. Trạng thái task mục tiêu

| Trạng thái | Ý nghĩa |
|---|---|
| PENDING / QUEUED | Đã lưu và chờ worker |
| RUNNING | Workflow đang xử lý |
| WAITING_APPROVAL | Đã lưu checkpoint, đang chờ quyết định của user |
| WAITING_USER_DATA | Đã lưu protocol/checkpoint; worker kết thúc, chờ upload hoặc thông tin user |
| PARTIAL | Có đầu ra hữu ích nhưng nêu rõ thiếu evidence/data/validation |
| COMPLETED | Đầu ra đạt các kiểm tra kỹ thuật đã định nghĩa |
| NEEDS_REVIEW | Cần người dùng kiểm tra do giới hạn/không giải quyết được lỗi |
| FAILED | Lỗi kỹ thuật không tạo được đầu ra |
| CANCELLED | User hủy task |

WAITING_* là trạng thái bền vững, không giữ HTTP connection hoặc worker task chạy trong nhiều ngày. Tải lên/quyết định mới phải authorize, persist và enqueue job resume idempotent.

## 5. Yêu cầu an toàn, riêng tư và chất lượng

- Tách authenticated user và task ownership trước khi nhiều người dùng truy cập.
- Xem web pages và upload là dữ liệu không tin cậy; chống prompt injection, SSRF, file quá cỡ/định dạng giả, malware và content độc hại.
- Không ghi secrets, access token, raw private documents hoặc dữ liệu định danh nhạy cảm trong log. Chốt retention/xóa trước khi nhận dữ liệu nghiên cứu nhạy cảm.
- Runner hạn chế quyền, non-root, resource/time limits, filesystem riêng, outbound network mặc định bị chặn; không chạy code trực tiếp trong Celery.
- Kiểm tra citation integrity tự động; đánh giá semantic support bằng rubric/dataset và người chấm. Không hứa loại bỏ hallucination.
- Log model/provider/version, token/usage, latency, retries và lỗi; budget guard trước mỗi lần gọi provider.
- Nghiên cứu human-subject phải hiển thị rõ protocol là draft và yêu cầu người dùng xin review/approval theo quy định tổ chức trước khi tuyển người/thu thập dữ liệu.
- Không phát hành cho người dùng thật nếu auth/ownership, upload security, retention và error handling chưa qua rà soát.

## 6. NFR và đánh giá

Ngưỡng số cụ thể chỉ chốt sau khi có baseline. Đánh giá tối thiểu cần version hóa query/dataset, nguồn tham chiếu, model/provider, config, rubric, người đánh giá và lỗi.

| Nhóm | Đo lường |
|---|---|
| Grounding | Citation resolves; semantic support; unsupported claim rate; coverage và source diversity |
| Research loop | Số nguồn/evidence mới mỗi vòng; dừng đúng khi không có delta; budget compliance |
| Analysis | Tái lập output từ routine/version/config/input; schema errors; chart/table provenance |
| Reliability | Job success/failure, retry/idempotency, resume correctness, stuck-task count |
| Performance/cost | p50/p95 theo task type, provider latency, tokens/API cost và chi phí mỗi task |
| Usability | User hiểu stage/warning/output type; hoàn tất các scenario mục tiêu |

## 7. Demo scope đến 10/11/2026

- **Core path cần ưu tiên:** câu hỏi → source web + upload PDF → tổng hợp/candidate gap có giới hạn → bài tổng quan có citation → theo dõi trạng thái và lưu provenance.
- **Experiment slice:** chỉ chọn một kiểu dữ liệu và routine thống kê/thuật toán có thể tái lập; nếu runner chưa an toàn/kịp hạn thì trình diễn protocol + dataset fixture với routine được duyệt ở mức local controlled, không tuyên bố chạy sandbox production.
- **Human-led path:** có thể hoàn thiện protocol và state WAITING_USER_DATA/resume nếu kịp; không thực hiện tuyển người hoặc hoạt động nghiên cứu ngoài hệ thống.
- **Non-core:** ảnh, PDF polished, hỗ trợ nhiều template/standard, collaboration.
- Mọi mục chưa có runtime evidence phải ghi “target/planned” hoặc “chưa xác minh”.

## 8. Acceptance gates trước phát hành

1. Migration có thể dựng database sạch; các quan hệ provenance có FK/constraint cần thiết.
2. Auth/ownership test cho mọi route, bao gồm chặn user truy cập task/file/report của người khác.
3. Upload validation, size/type limits, storage access control, retention/deletion được xác định.
4. Worker start/fail/retry/cancel/resume có trạng thái bền vững, idempotency và event hợp lệ.
5. Một workflow đầu cuối dùng provider có kiểm soát hoặc mock được lưu bằng chứng; budget limit thực thi trước mỗi call.
6. Citation integrity và kết quả analysis có lineage; semantic evaluation được báo cáo riêng.
7. Không tạo Results nếu chưa có dữ liệu; human research protocol có ethics notice.
8. Không đánh dấu các kiến trúc target (SSE, runner, upload, WAITING_USER_DATA...) là đã hoàn thành nếu chưa chạy xác minh.
