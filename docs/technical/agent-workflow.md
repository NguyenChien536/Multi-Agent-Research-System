# LangGraph Agent Workflow — hiện trạng và thiết kế mục tiêu

**Cập nhật tài liệu:** 06/10/2026. Runtime evidence gần nhất trong [baseline-verification.md](../project/baseline-verification.md) được thu 27/09/2026. Đọc source hiện tại không đồng nghĩa xác nhận runtime; không chạy research workflow trong lượt cập nhật docs.

## 1. Nguyên tắc

ATI là workflow có nhiều vai trò/agent node được điều phối bởi LangGraph, không phải tập agent độc lập có quyền tự quyết. AI hỗ trợ từng bước; người dùng giữ quyền với kế hoạch, nghiên cứu ngoài hệ thống và quyết định quan trọng. Outputs phải giữ provenance.

## 2. Vai trò trong workflow mục tiêu

| Vai trò / node | Trách nhiệm target | Ràng buộc |
|---|---|---|
| Supervisor | Phân loại study type, dựng plan, xác định budget, report type và đường đi | Không tự phê duyệt nghiên cứu/ethics |
| Researcher | Tìm web, truy vấn bổ sung có mục tiêu; safe fetch | Query có giới hạn; kiểm tra URL/SSRF; dừng nếu không có evidence mới |
| Curator | Khử trùng, chuẩn hóa, chunk, embed web/upload sources | Kiểm tra file; không tin cậy nội dung/prompt trong nguồn |
| Evidence Analyst | Trích claim/quote, nguồn/chunk, mâu thuẫn và độ bất định | Mỗi claim phải có lineage hoặc gắn nhãn thiếu evidence |
| Synthesis / Gap Analyst | Tổng hợp đồng thuận, tranh luận, giới hạn và candidate research questions | Nêu search scope; không khẳng định gap toàn ngành |
| Methodology Designer | Đề xuất hypothesis/question, method, protocol, data plan và article type | Protocol human study là draft, cần review phù hợp |
| Data / Experiment Analyst | Chọn routine hỗ trợ, diễn giải output bảng/biểu đồ từ dữ liệu thật | Chỉ chạy trong isolated runner; không chạy arbitrary LLM code |
| Writer | Viết theo cấu trúc đúng với loại đầu ra | Không bịa citations/results; thiếu data thì không viết empirical findings |
| Critic | Kiểm tra evidence, phương pháp, coverage, giới hạn; phát verdict | Không phải peer reviewer độc lập |
| Citation / Artifact Validator | Xác nhận source/chunk/report và input/output artifact lineage | Referential integrity không đồng nghĩa semantic correctness |

Các vai trò trong cột này là **target design**. Source hiện có một phần node tương ứng, chưa đồng nghĩa đã chạy được toàn workflow.

## 3. State mục tiêu cần lưu bền vững

Target state nên chứa: task/user ID; question/scope/study type/mode/report type; plan versions và user decision; provider/resource budget; sources/chunks/vectors; claims/evidence/citation lineage; macro/micro counters; checkpoint/status; input/protocol/result/chart/report artifact IDs; run metadata, warning và errors.

WAITING_APPROVAL và WAITING_USER_DATA là trạng thái bền vững. Graph checkpoint lưu vào DB; Celery job hiện tại kết thúc. Khi user decision/upload được authorize và persist, API enqueue một resume job idempotent. Không giữ HTTP request hay worker job trong nhiều ngày.

## 4. Target routing và bounded loops

- Supervisor → optional approval → source discovery/ingestion → evidence analysis → candidate gap/synthesis → method selection.
- Literature/review path đi Writer bằng evidence hiện có.
- Computational path chỉ chạy data schema/routine được hỗ trợ, sau khi user cung cấp data và duyệt cấu hình; chạy ở isolated runner, không trong API/Celery.
- Lab/survey/field/human-participant path chỉ xuất protocol/ethics notice, chuyển WAITING_USER_DATA và chờ user mang kết quả được phép xử lý về.
- Writer ↔ Critic micro-loop bị giới hạn bởi max revision.
- Critic có thể yêu cầu macro-loop tìm evidence cụ thể; tối đa 3 vòng, dừng sớm nếu không có nguồn/evidence mới sau dedup.
- Budget, timeout và retry limit được kiểm tra trước mỗi provider call.
- PASS dẫn đến deterministic citation/artifact validation; đầu ra mang trạng thái COMPLETED/PARTIAL/NEEDS_REVIEW. Citation validator không chứng minh semantic correctness.
- Không có actual data thì output là review/protocol/draft thiếu phần; không tạo empirical Results.

Sơ đồ điều khiển chuẩn: [System Design — Inference Flow](../architecture/system-design.md#4-inference-flow--multi-agent-workflow).

## 5. Source inventory và baseline evidence

| Phần | Source inventory khi đọc ngày 06/10 | Runtime evidence |
|---|---|---|
| State / routing | Agent state, graph và node modules có trong repository | Graph import/compile và 5 routing case mẫu pass tại baseline 27/09; chưa invoke toàn graph |
| Supervisor, Researcher, Curator, Analyst, Writer, Critic | Các node hiện hữu trong source | Provider thật, end-to-end loop và quality chưa được kiểm tra |
| Worker | Worker gọi graph async invoke, cập nhật task status/report trong source | Celery ping đạt; chưa gửi research task thật |
| Claim/evidence | Source đã khai báo ClaimEvidence junction và Citation.chunk_id nullable; có migration mới trong working tree | Thay đổi sau baseline chưa áp dụng/xác minh trên DB sạch hoặc runtime |
| Auth | Source có registration endpoint; research API còn dùng dummy user ID | Login/token/ownership chưa được xác minh |
| Search/retrieval | Tavily, fetch, embedding, vector retrieval trong source | Chưa E2E với credentials/provider thật |
| Upload, durable HITL, WAITING_USER_DATA, experiment runner, full monitoring | Chưa thấy implementation đủ trong baseline/source inventory đã ghi | Chưa xác minh |

Không dùng source inventory để kết luận feature hoàn tất. Giữ nguyên working tree hiện có; không thay đổi source code trong lượt cập nhật tài liệu.

## 6. Việc kỹ thuật theo thứ tự

1. Khóa dependency/runtime, DB sạch và Alembic upgrade; review migration mới trước khi áp dụng.
2. Hoàn thành authentication/token và kiểm tra ownership cho mọi task/report/file route.
3. Chốt task state machine, budgets, idempotency, error state và worker dispatch/retry.
4. Hoàn thiện source/upload validation, safe fetch, source/chunk/evidence/citation lineage.
5. Test workflow bằng mock provider trước; chạy provider thật chỉ sau khi đặt quota/cost cap.
6. Chọn analysis runner bằng ADR/threat model; nếu chưa đủ an toàn thì không chạy arbitrary/generated code.
7. Chứng minh durable WAITING_APPROVAL/WAITING_USER_DATA + resume, progress delivery và monitoring.
8. Đánh giá chất lượng grounding/report bằng dataset versioned và rubric; tách citation integrity khỏi semantic support.
