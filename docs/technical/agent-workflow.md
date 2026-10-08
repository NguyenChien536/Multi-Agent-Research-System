# Agent Workflow — vai trò, điều phối và kiểm tra

**Chốt thiết kế:** 08/10/2026. Xem [SRS](../requirements/SRS.md), [System Design](../architecture/system-design.md), [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md).

## 1. Agent và công cụ khác nhau thế nào?

ATI là workflow đa tác tử điều phối bằng LangGraph. Agent dùng LLM để đưa ra đầu ra có cấu trúc; router và guards bằng code quyết định có được hành động/chuyển bước hay không. Không để agent tự sinh thêm agent hoặc tool ngoài allowlist.

| Agent | Đầu vào | Đầu ra có cấu trúc | Ràng buộc |
|---|---|---|---|
| Supervisor | Câu hỏi, output type, constraints, budget | Plan version, phạm vi, bước/role cần dùng, đề xuất route | Không tăng cap, bỏ ownership hoặc tự nhận ethics approved |
| Researcher | Plan, câu hỏi còn thiếu, nguồn hiện có | Search queries, source candidates, search log | Tìm cả bằng chứng trái chiều; giới hạn query/provider calls |
| Evidence Analyst | Chunks có ID, retrieval results | Claims, evidence anchors/quotes, mâu thuẫn, tổng hợp và gợi ý gap | Gap chỉ trong corpus/search scope; không bỏ source/chunk IDs |
| Methodologist | Question/gap, evidence, data availability | Giả thuyết có thể kiểm tra, method, protocol, tiêu chí đo/giới hạn | REVIEW có thể bỏ role này; method không hỗ trợ phải nói rõ |
| Data Analyst | Dataset schema, method/config, output runner | Đề xuất routine cho phép; diễn giải metrics/charts đã chạy | Không tạo metric bằng suy đoán, không chạy arbitrary code |
| Writer | Output schema, evidence, protocol/results được xác nhận | Bản nháp theo loại bài, claim references, limitations | Thiếu dữ liệu không viết Results như đã quan sát |
| Critic | Toàn bộ draft theo sections, evidence, plan/method, artifacts | PASS / REVISE / NEED_EVIDENCE / NEED_METHOD_REVIEW và issues có anchor | Phản biện nội dung/phương pháp; không tự phê duyệt ngoại lệ, không thay peer review |

Mỗi lượt có agent_run_id, prompt/model version, input references, output schema, duration và usage. Model có thể dùng chung; lợi ích cần đo qua phân vai/context/feedback, không suy ra từ số model.

## 2. Mô-đun xác định bằng code

- **Curator/Ingestion:** validate, dedup, parse PDF/web, chunk, embed và lưu provenance.
- **Router/State machine:** allowlisted transitions; lifecycle tách stage; optimistic version/CAS.
- **Budget manager:** reserve/reconcile cho LLM/search/embedding, retry/fallback và job tài nguyên.
- **Citation/Artifact Validator:** cùng task/owner, anchor tồn tại, quote khớp, report-claim-evidence lineage và manifest thực nghiệm.
- **Runner adapter/launcher:** routine registry/config schema, staging và giới hạn; không cho worker Docker socket.
- **ArtifactStore và event publisher:** file private/checksum, event bền vững và thông báo tiến độ.

Đây không phải các agent LLM bổ sung.

## 3. State và hợp đồng chuyển bước

State graph giữ task_id, run_id, owner_id, plan/version, output/study path, source/evidence/artifact/report IDs, counters, budgets, checkpoint ID và warnings. Full documents/file bytes nằm trong DB/storage. Node trả immutable delta, không sửa ngầm list lồng nhau đã tích lũy.

Plan phải chỉ rõ: loại output, phạm vi, nguồn dự kiến, phương pháp, dữ liệu cần có, calls/cost/time cap và điều kiện dừng. Assisted yêu cầu user duyệt tại gate; Automatic chỉ tự đi tiếp trong policy đã chọn. Thay phương pháp hoặc vượt policy phải chờ quyết định; không có chế độ tự bỏ guard.

WAITING_APPROVAL và WAITING_USER_DATA là trạng thái bền vững: checkpoint và quyết định được ghi DB, worker job kết thúc. Resume phải kiểm owner, plan_version, checkpoint, file READY và idempotency key. Upload cũ/decision lặp không tạo thêm run hoặc lặp side effect.

WAITING_* vẫn là active run của task, nhưng không giữ worker lease. Sửa plan trong run giữ run_id/counters/budget; sửa bài sau terminal tạo run mới. Tombstone thu hồi quyền resume/ghi kết quả ngay; cancellation được xử lý tại safe boundary. Bảng chuyển trạng thái chuẩn nằm ở [Data Model & API §3](data-model-and-api.md#3-vòng-đời-và-event).

## 4. Luồng và research loop

1. Supervisor lập plan; chuẩn hóa/kiểm policy; duyệt nếu cần.
2. Researcher + ingestion thu thập nguồn web/PDF. Evidence Analyst tạo evidence/claims và gợi ý khoảng trống nghiên cứu có giới hạn.
3. REVIEW đi Writer. EMPIRICAL gọi Methodologist/Data Analyst và runner khi data/config hợp lệ. PROTOCOL gọi Methodologist rồi Writer; có thể xuất protocol đã kiểm hoặc chờ data để tiếp tục.
4. Writer → Critic → deterministic validation. Protocol cũng qua chuỗi này.
5. Critic NEED_EVIDENCE chỉ rõ câu hỏi/claim thiếu; Researcher tìm bổ sung có mục tiêu. REVISE đưa issues cho Writer; NEED_METHOD_REVIEW quay lại plan gate, không chạy lặp để tìm kết quả mong muốn.

| Guard | Quy tắc |
|---|---|
| Thu thập nguồn | Tối đa 3 rounds, tính cả lần đầu |
| No evidence delta | Dừng vòng thu thập khi không thêm evidence sau dedup; giữ giới hạn trong output |
| Writer revision | Tối đa 2 lần sau draft đầu; sửa citation tính vào cùng counter |
| Method change | Version plan mới, kiểm user policy; không dùng lại Results của config/data cũ |
| Provider budget | Kiểm trước mọi call/retry/fallback, reserve atomic theo run |
| Hết cap | Dừng calls; giữ draft, metadata và nguyên nhân; không tự tăng cap |

Không dùng vòng feedback để “chứng minh” giả thuyết hoặc sửa số liệu. Kết quả phủ định cũng là đầu ra hợp lệ.

## 5. Kết thúc và trải nghiệm người dùng

- **COMPLETED:** output đúng loại, mandatory gates đạt, provenance hợp lệ; không đồng nghĩa nghiên cứu đã được công nhận khoa học.
- **PARTIAL:** output còn hạn chế/thiếu coverage nhưng phần được công bố có lineage hợp lệ và limitations rõ.
- **NEEDS_REVIEW:** lỗi method/lineage hoặc quyết định chưa giải quyết; không xuất như bài hoàn tất.
- **FAILED/CANCELLED:** không tạo Results hay báo thành công; giữ error và dữ liệu bàn giao phù hợp.
- Q&A dùng report/evidence version hiện có, có operation ID/cap riêng trong quota task qua cùng budget adapter; không reset budget research run. Yêu cầu nghiên cứu mới sau terminal tạo run mới có cap; nếu đang active thì xử lý theo plan gate hoặc trả 409. Revision lưu version, không ghi đè bản đã dùng để đánh giá.
- UI hiển thị role/stage, sự kiện, output summary, chi phí ước tính và việc cần người dùng làm; không cần hiển thị chain-of-thought.

## 6. Khoảng cách với source

Rà soát source `ebb525a` ngày 08/10: đã có Supervisor/Researcher/Curator/Analyst/Writer/Critic và graph, nhưng Curator hiện là code ingestion; chưa có đầy đủ method/data roles. Graph chưa gắn durable checkpointer; worker chưa đưa budget vào initial state; Analyst mất chunk UUID trong output; postprocessor chưa validate citation; Critic chỉ đọc prefix draft. Auth/ownership và lifecycle là blockers trước khi mở rộng roles.

Đây là nhận xét đọc code, không phải kết quả chạy. Runtime cũ ghi tại [Baseline](../project/baseline-verification.md). Khắc phục theo [Implementation Plan](../project/implementation-plan.md); đo ích lợi của multi-agent theo [Evaluation Plan](../project/evaluation-plan.md).
