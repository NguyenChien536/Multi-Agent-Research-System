# Đánh giá sản phẩm và quyết định scope

## 1. Định vị sản phẩm

ATI là **research orchestrator / co-scientist có người giám sát**: hỗ trợ tìm và tổng hợp nguồn, nêu candidate research questions/gaps theo phạm vi đã xem, gợi ý giả thuyết/phương pháp/protocol, phân tích một số dữ liệu được hỗ trợ, và tạo bài viết theo đúng loại đầu ra.

ATI không tuyên bố là AI Scientist tự chủ hoàn toàn, systematic review tự động, peer reviewer độc lập, hay chuyên gia thay nhà nghiên cứu. Với nghiên cứu cần lab, thực địa, khảo sát hoặc người tham gia, hệ thống soạn tài liệu để nhà nghiên cứu tự xin review và thực hiện ngoài ATI.

## 2. Bài toán và giá trị cần kiểm chứng

| Pain point | Hướng giải quyết | Bằng chứng cần thu thập |
|---|---|---|
| Tìm kiếm/đọc nhiều nguồn mất thời gian | Search + user source upload + evidence synthesis | Thời gian và độ bao phủ trên query set |
| Claim AI khó kiểm chứng | Claim → evidence → chunk → source lineage | Citation integrity và semantic support chấm riêng |
| Gap/hypothesis dễ bị nói quá chắc chắn | Trình bày candidate, search scope, uncertainty và counterevidence | Rubric đánh giá mức phù hợp/độ thận trọng |
| Bài báo thực nghiệm cần dữ liệu thật | Protocol/data plan + supported analysis hoặc user-supplied results | Tái lập input, routine, config, output và provenance |
| Quy trình dài có điểm cần con người | Durable checkpoints, WAITING_APPROVAL/WAITING_USER_DATA, resume job | Resume test và usability scenario |
| Người dùng không biết agent đang làm gì | Stage/state/progress, warnings, structured logs | Scenario testing, latency/errors/cost dashboard |

## 3. Quy tắc nội dung sản phẩm

- Research gap luôn là **candidate gap within reviewed sources** và nêu search limits.
- “Có citation” không đồng nghĩa claim được evidence hỗ trợ; validate liên kết và đánh giá semantic là hai việc.
- Không tự tạo số liệu; Results chỉ từ dataset/analysis thật hoặc dữ liệu tổng hợp do nhà nghiên cứu cung cấp có provenance.
- Article type/section template phụ thuộc loại nghiên cứu và phạm vi hỗ trợ; không hứa mọi reporting guideline trước khi mapping/validation.
- Critic agent không được quảng bá là peer review.
- Protocol cho human subjects là draft, cần review/approval theo cơ sở/ngành; ATI không tuyển người và không mở nút bắt đầu nghiên cứu.
- Uploaded content không tin cậy; xử lý bảo mật/quyền sở hữu/retention phải được xác định.

## 4. Phạm vi demo và sau demo

| Release slice | Bao gồm | Không hứa |
|---|---|---|
| Demo trước 10/11 | Literature research end-to-end; web + upload paper; bounded research loop; candidate questions; citation/evidence; progress; Markdown report | Mọi loại bài báo, hiệu năng production, zero hallucination |
| Demo analysis slice (nếu safety gate đạt) | Một loại dataset + một routine phân tích tái lập; output thật có bảng/biểu đồ/provenance | Chạy mã LLM tùy ý hoặc nhiều domain/routine |
| Human-led study target | Protocol/checklist/ethics notice; durable WAITING_USER_DATA; resume sau khi tải kết quả được phép | Tuyển người/thu thập lab hoặc ethics approval thay người dùng |
| Sau demo | Mở rộng article templates, methods/routines, PDF/image, richer monitoring, multi-user/privacy, collaboration theo điều kiện | Bật các năng lực chưa qua acceptance/security review |

## 5. Evaluation plan

So sánh với baseline prompting/RAG chỉ khi giữ cùng query, evidence corpus, model/budget và rubric. Đo citation resolves, semantic support, coverage, diversity, unsupported claims, source freshness/reliability, latency, failure rate, cost, resume reliability và người dùng có hiểu warning/trạng thái không. Dùng dataset versioned; không công bố “tốt hơn” trước khi có kết quả.
