# System Architecture — High-Level Design

**Cập nhật:** 09/10/2026 · **Trạng thái:** thiết kế mục tiêu; chưa phải hệ thống đã nghiệm thu.

## 1. Định hướng

**ATI — Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập.** Đầu ra cuối của mỗi task là bản thảo bài báo hoàn chỉnh theo loại: review hoặc empirical paper. Hệ thống hỗ trợ tổng quan tài liệu, một phạm vi phân tích tính toán được kiểm soát, và protocol **trung gian** cho nghiên cứu con người thực hiện bên ngoài trước khi nạp kết quả thực để viết bài. Bản thảo đúng cấu trúc và có căn cứ không đồng nghĩa đã được peer review hoặc đủ điều kiện công bố.

[SRS](../requirements/SRS.md) chốt yêu cầu; [System Design](system-design.md) là nguồn chuẩn sơ đồ; [User Journey](../project/user-journey-and-outputs.md) chốt trải nghiệm/đầu ra; [ADR-004](decisions/ADR-004-multi-agent-research-delivery.md) chốt quyết định; [Implementation Plan](../project/implementation-plan.md) chốt thứ tự xây dựng.

Ma trận chức năng, technology và patterns nằm tại [Technical Design](technical-design.md); HLD tập trung boundary, trách nhiệm và đánh đổi.

## 2. Kiến trúc được chọn

**Modular monolith:** giữ một codebase backend với API và worker chạy ở các process riêng. Agent là vai trò trong graph, không phải microservice. Dùng stack hiện có; chưa cần Kubernetes, Kafka, vector database riêng hoặc hệ thống memory dài hạn.

| Thành phần | Trách nhiệm | Quyết định và đánh đổi |
|---|---|---|
| Next.js UI | Danh sách nhiều bài, tạo workspace, thêm nguồn, xem plan/agent progress, Q&A, sửa/xuất bài | Timeline phản ánh event thực; bài chờ có action rõ; polling dùng được trước SSE |
| FastAPI | Auth/ownership, vòng đời task/run, upload, duyệt, resume, report access | Request ngắn; background dispatcher chuyển outbox sang broker |
| Redis | Celery broker và thông báo tiến độ | Không giữ trạng thái nghiên cứu duy nhất |
| Celery + LangGraph | Chạy graph, gọi provider, phối hợp agent, checkpoint | Delivery có thể lặp; mỗi side effect phải có định danh và dedup |
| PostgreSQL + pgvector | Task/run/plan versions, evidence, reports, events, experiment journal, outbox, vector | Một DB giảm vận hành; journal append-only riêng với event UI, pin embedding profile và lọc ownership |
| ArtifactStore | PDF, CSV, protocol, metrics/charts và exports | Private local volume cho bản nộp; interface cho S3-compatible sau này |
| Analysis runner | Chạy routine do dự án viết/duyệt trong container riêng | Host launcher tin cậy; API/worker không có Docker socket; không nhận mã LLM tùy ý |
| Telemetry | JSON logs, AgentRun, TaskEvent, duration/usage/errors | Là năng lực của API/worker và DB, không bắt buộc một dịch vụ observability mới |

Providers ngoài gồm search, public websites, LLM/embedding; ảnh là tùy chọn sau core. Lab/khảo sát/thực địa thuộc hoạt động của người dùng ngoài ATI. File riêng chỉ được tải qua API có kiểm tra quyền; không mở trực tiếp storage ra Internet.

## 3. Multi-agent có trách nhiệm rõ

Bảy vai trò: **Supervisor, Researcher, Evidence Analyst, Methodologist, Data Analyst, Writer, Critic**. Evidence Analyst kiêm tổng hợp và gợi ý khoảng trống nghiên cứu. REVIEW chủ yếu dùng năm vai trò; Methodologist/Data Analyst được gọi theo nhu cầu. Có thể dùng chung model với context/contract riêng.

Curator/ingestion, router, validator, budget manager và runner là mô-đun xác định bằng code. Supervisor đề xuất route trong schema; code kiểm điều kiện chuyển trạng thái. Critic đọc cả bài, evidence và phương pháp; không chỉ phản biện văn phong và không được gọi là peer reviewer độc lập.

Xem [Agent Workflow](../technical/agent-workflow.md) cho hợp đồng từng vai trò.

## 4. Ba đường đi, mỗi bài một workspace

| Đường đi | Xử lý | Đầu ra hợp lệ |
|---|---|---|
| REVIEW | Web/PDF → evidence → tổng hợp/gợi ý gap → viết → phản biện/validate | Bài tổng quan có nguồn, phạm vi tìm kiếm và giới hạn |
| EMPIRICAL_COMPUTATIONAL | Evidence + phương pháp + CSV hợp lệ → routine → actual results → viết/kiểm tra | Bài thực nghiệm, bảng/biểu đồ và gói tái lập |
| EMPIRICAL_HUMAN | Evidence + phương pháp → protocol/biểu mẫu → WAITING_USER_DATA → nhận kết quả thực → viết/kiểm tra | Bài thực nghiệm với provenance kết quả người dùng nạp; protocol chỉ là artifact trung gian |

Nếu tiếp tục nghiên cứu bên ngoài: lưu checkpoint, chuyển WAITING_USER_DATA, kết thúc worker job. Upload hợp lệ tạo yêu cầu resume gắn đúng plan/checkpoint/version. Method ngoài khả năng routine chỉ được hướng dẫn hoặc diễn giải kết quả người dùng cung cấp có provenance, không tự nhận đã chạy phân tích.

Routine tham chiếu của bản nộp là `tabular_regression_v1`: mô tả CSV numeric và so sánh baseline với Ridge bằng cấu hình cố định. Journal giữ plan trước chạy, mọi attempt/kết quả âm và phép chạy lại riêng; log vận hành không thay journal. Đây là lát cắt chứng minh thực thi/tái lập, không giới hạn tổng quan và protocol vào AI/ML. Chi tiết tại [ADR-004](decisions/ADR-004-multi-agent-research-delivery.md) và [ADR-005](decisions/ADR-005-experiment-journal-and-reproducibility.md).

## 5. State, reliability và ngân sách

- ResearchTask là workspace **của một bài**; ResearchRun là một lần nghiên cứu/sửa; chỉ một active run/task nhưng một user có nhiều task. Lifecycle status khác stage/agent đang chạy.
- WAITING_* vẫn chiếm active run của chính task, nhưng trả worker lease và không chiếm quota RUNNING của user. User mở/chạy bài khác; tối đa 2 job RUNNING/user, QUEUED đợi bền vững theo dispatcher. Revise plan đang active giữ run/budget; revision sau terminal tạo run mới. Q&A đọc report version qua operation/cap riêng, không mở lại run đã kết thúc.
- API ghi task/run/outbox trong cùng transaction. Dispatcher nền trong API lifespan publish và retry; worker claim/lease, kiểm version và dedup. Không hứa exactly-once cho provider.
- Checkpointer PostgreSQL giữ namespace riêng. State graph chủ yếu gồm IDs/counters; không nhồi file bytes hoặc toàn văn vào checkpoint. Version thư viện phải được pin trước khi áp dụng API interrupt/resume.
- TaskEvent lưu DB trước khi phát thông báo Pub/Sub. SSE dùng event ID để replay hoặc trả snapshot; mất Redis event không mất trạng thái.
- Tối đa **3 vòng thu thập tính cả vòng đầu**, **2 lần sửa sau bản nháp đầu**; sửa citation dùng chung hạn mức sửa. Không có evidence mới sau dedup thì dừng vòng thu thập.
- Mọi LLM/search/embedding call, retry và fallback đi qua budget adapter reserve/reconcile. Model/embedding profile được pin; đổi embedding phải re-index corpus.
- Citation lineage là kiểm tra kỹ thuật; semantic support cần Critic và đánh giá con người riêng. COMPLETED chỉ khi các gate phù hợp loại output đạt; PARTIAL có giới hạn công khai; NEEDS_REVIEW không được phát hành như bản hoàn tất.

## 6. Ranh giới dữ liệu và runner

Upload kiểm magic bytes, kích thước, schema và quyền; fetch chặn địa chỉ nội bộ, giới hạn response/timeout và kiểm điểm kết nối thực tế. Nội dung nguồn là dữ liệu không tin cậy, không được dùng làm chỉ dẫn hệ thống.

Launcher chỉ nhận routine/config thuộc allowlist, stage file theo job; container non-root, read-only rootfs, no network, drop capabilities, giới hạn CPU/RAM/time/output. Giới hạn này phục vụ **routine tin cậy trong môi trường kiểm soát**, không phải bảo đảm sandbox cho mã đối kháng. Mở chạy mã tự sinh cần threat model, execution boundary được kiểm an toàn, đánh giá chất lượng/tái lập đủ mạnh và ADR chọn công nghệ riêng; tiêu chí tại [Experiment Journal](../technical/experiment-journal-and-reproducibility.md#5-điều-kiện-mở-rộng-sang-mã-do-ai-tạo).

Q&A chỉ đọc report version/evidence; sửa tạo version mới. Thay dữ liệu/phương pháp tạo plan/run mới và vô hiệu hóa kết quả cũ. Log giữ IDs, status, timing, usage, lỗi đã che dữ liệu; không công bố raw reasoning nội bộ hay secrets.

Xóa task tombstone và chặn truy cập/resume/late writes ngay, worker/launcher cancel tại safe boundary. Cleanup có retry theo NFR-07; yêu cầu đã gửi provider có thể vẫn kết thúc nhưng không được phát hành vào task đã xóa. Gate và trách nhiệm triển khai được ánh xạ tại [SRS §8–9](../requirements/SRS.md#8-acceptance-gates).

## 7. Phạm vi bàn giao và bằng chứng

Đến 10/11: review web+PDF; một experiment thật; protocol/wait/resume; Q&A/revision cơ bản; Markdown/experiment export; progress/log; ownership/budget/lineage; đánh giá multi-agent. PDF đẹp, ảnh, methods/template bổ sung, cộng tác và vận hành production rộng để sau.

Đọc source tại `ebb525a` ngày 08/10 cho thấy nhiều nền tảng mới chỉ có một phần. Lần runtime được ghi nhận gần nhất là 27/09, không xác minh các thay đổi sau đó. Xem [Product Assessment](../project/product-assessment.md) và [Baseline Verification](../project/baseline-verification.md); sơ đồ không phải bằng chứng feature đã chạy.
