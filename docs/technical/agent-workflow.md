# Agent Workflow — vai trò, điều phối và kiểm tra

**Cập nhật thiết kế:** 09/10/2026. Xem [SRS](../requirements/SRS.md), [System Design](../architecture/system-design.md), [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md).

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

WAITING_* vẫn là active run của **task đó**, nhưng không giữ worker lease/quota RUNNING; user có thể tạo/chạy task khác. Sửa plan trong run giữ run_id/counters/budget; sửa bài sau terminal tạo run mới. Tombstone thu hồi quyền resume/ghi kết quả ngay; cancellation được xử lý tại safe boundary. Bảng chuyển trạng thái chuẩn nằm ở [Data Model & API §3](data-model-and-api.md#3-vòng-đời-và-event).

## 4. Luồng và research loop

1. Supervisor lập plan; chuẩn hóa/kiểm policy; duyệt nếu cần.
2. Researcher + ingestion thu thập nguồn web/PDF. Evidence Analyst tạo evidence/claims và gợi ý khoảng trống nghiên cứu có giới hạn.
3. REVIEW đi Writer. EMPIRICAL_COMPUTATIONAL gọi Methodologist/Data Analyst và runner khi data/config hợp lệ. EMPIRICAL_HUMAN gọi Methodologist, tạo protocol/biểu mẫu đã review rồi WAITING_USER_DATA; sau khi nạp kết quả thật mới đi Writer cho bài báo hoàn chỉnh.
4. Writer → Critic → deterministic validation. Protocol trung gian cũng được review, nhưng không đi tới `COMPLETED`.
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

- **COMPLETED:** bài báo đúng loại, đủ các phần/Results thật bắt buộc, mandatory gates đạt, provenance hợp lệ; không đồng nghĩa nghiên cứu đã được công nhận khoa học.
- **PARTIAL:** output còn hạn chế/thiếu coverage nhưng phần được công bố có lineage hợp lệ và limitations rõ.
- **NEEDS_REVIEW:** lỗi method/lineage hoặc quyết định chưa giải quyết; không xuất như bài hoàn tất.
- **FAILED/CANCELLED:** không tạo Results hay báo thành công; giữ error và dữ liệu bàn giao phù hợp.
- Q&A dùng report/evidence version hiện có, có operation ID/cap riêng trong quota task qua cùng budget adapter; không reset budget research run. Yêu cầu nghiên cứu mới sau terminal tạo run mới có cap; nếu đang active thì xử lý theo plan gate hoặc trả 409. Revision lưu version, không ghi đè bản đã dùng để đánh giá.
- UI hiển thị danh sách nhiều bài, role/stage của từng bài, sự kiện, output summary, chi phí ước tính và việc cần người dùng làm; không cần hiển thị chain-of-thought. Xem [User Journey](../project/user-journey-and-outputs.md).

## 6. Khoảng cách với source

Rà soát source `ebb525a` ngày 08/10: đã có Supervisor/Researcher/Curator/Analyst/Writer/Critic và graph, nhưng Curator hiện là code ingestion; chưa có đầy đủ method/data roles. Graph chưa gắn durable checkpointer; worker chưa đưa budget vào initial state; Analyst mất chunk UUID trong output; postprocessor chưa validate citation; Critic chỉ đọc prefix draft. Auth/ownership và lifecycle là blockers trước khi mở rộng roles.

Đây là nhận xét đọc code, không phải kết quả chạy. Runtime cũ ghi tại [Baseline](../project/baseline-verification.md). Khắc phục theo [Implementation Plan](../project/implementation-plan.md); đo ích lợi của multi-agent theo [Evaluation Plan](../project/evaluation-plan.md).

## 7. Quy cách bản thảo — cập nhật 29/10/2026 (#61, #63)

Supervisor gắn `manuscript_contract` phiên bản 2 vào kế hoạch mới. Contract được lưu cùng checkpoint và giữ qua bước duyệt/tiếp tục. Các chủ đề LLM đề xuất nằm bên trong phần phân tích; LLM không tự bỏ khung bài bắt buộc. Bản thảo cũ giữ contract và kết quả đánh giá lúc tạo, không bị đánh giá lại ngầm bằng quy tắc mới.

| Loại nghiên cứu | Dạng bản thảo mặc định | Các phần chính sau Title, Abstract, Keywords, Introduction |
|---|---|---|
| REVIEW | Tổng quan phân tích tài liệu / narrative review | Related Work; Literature Search and Scope; Thematic Synthesis; Discussion; Limitations; Conclusion |
| EMPIRICAL_COMPUTATIONAL | Bài thực nghiệm tính toán trong routine được hỗ trợ | Related Work; Methods; Experimental Setup; Results; Discussion; Limitations; Conclusion |
| EMPIRICAL_HUMAN | Bài thực nghiệm từ dữ liệu người dùng cung cấp | Related Work; Methods; Results; Discussion; Limitations; Conclusion |

Các tiêu đề được bản địa hóa theo ngôn ngữ bài. References được dựng từ claim/evidence đã xác minh sau khi viết, không lấy bibliography do model tự tạo. Citation style và bố cục manuscript là hai cấu hình khác nhau; khung này không phải template xuất bản của một tạp chí cụ thể.

Introduction đi từ bối cảnh đến vấn đề cụ thể, câu hỏi nghiên cứu (RQ1/RQ2), khoảng trống giới hạn trong tài liệu đã kiểm tra, cách tiếp cận và đóng góp thực tế. Related Work đối chiếu phương pháp, giả định và hạn chế bằng trích dẫn. Tổng quan đóng góp bằng tổng hợp/đối chiếu bằng chứng; một thiết kế chưa thử nghiệm được ghi là đề xuất, không thành Results.

Writer phải dùng đoạn văn phát triển luận điểm, đối chiếu nguồn, diễn giải và nêu giới hạn. Danh sách ngắn cho câu hỏi nghiên cứu/protocol vẫn hợp lệ; nếu hơn 25% số từ phần văn bản chính nằm trong ít nhất ba mục liệt kê, bộ kiểm tra yêu cầu sửa. Đây là ngưỡng biên tập của sản phẩm, không phải quy tắc cấm danh sách trong mọi bài báo.

`search_activity` chỉ ghi truy vấn đã gọi search thành công, provider, số URL ứng viên, số nguồn lấy được và thời điểm. Truy vấn dự kiến không được biến thành nhật ký thực hiện. Nguồn đã lưu từ lần trước và PDF tải lên được mô tả đúng xuất xứ. REVIEW hiện không thực hiện protocol tổng quan hệ thống; Writer không được tự nhận PRISMA, sàng lọc độc lập, bao phủ đầy đủ hoặc truy vấn trực tiếp Scopus/PubMed/IEEE Xplore khi chỉ dùng web search.

Critic kiểm toàn bộ bài cùng contract, provenance và các phát hiện từ bộ kiểm tra xác định. Thiếu tiêu đề/phần bắt buộc, phần rỗng, sai thứ tự, văn bản thiên về liệt kê hoặc dấu hiệu tự nhận phương pháp không có hồ sơ phải quay về Writer trong giới hạn hai vòng sửa. Trước khi giao bài, PostProcessor kiểm tra lại độc lập; lỗi còn tồn tại buộc `NEEDS_REVIEW`, dù LLM trả PASS. Bản cũ vẫn giữ kết quả review theo chính sách đã dùng khi tạo; khi tạo phiên bản mới thì áp dụng contract mới.

Kiểm tra cấu trúc và heuristic phương pháp không chứng nhận độ đúng khoa học, độ tin cậy của nguồn hoặc phát hiện mọi cách diễn đạt sai. Critic vẫn là đánh giá nội bộ; người nghiên cứu cần rà soát phương pháp, bằng chứng và yêu cầu nơi dự định nộp. Nguyên tắc tham khảo: [ICMJE manuscript preparation](https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html) và [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020-checklist).

### Hình, số liệu và mẫu trình bày

- Sơ đồ xử lý bằng chứng được ghi rõ là hình khái niệm. Biểu đồ MAE chỉ được tạo khi routine đã chạy thành công và có cả baseline/model; giá trị, số hàng test và provenance được đóng băng cùng phiên bản. Không để LLM tự vẽ số liệu.
- Writer phải giải thích từng Figure trong văn bản, dùng caption và marker tài sản do hệ thống cấp. Kiểm tra trước giao bài bắt hình thiếu/không giải thích, một số số liệu MAE sai, claim vượt trội hoặc ý nghĩa thống kê không có hồ sơ. Kiểm tra tái lập cùng seed không chứng minh ý nghĩa thống kê hay khả năng khái quát.
- Người dùng có thể chọn **IEEE Conference** hoặc **ACM SIGCONF** và tải **ZIP nguồn LaTeX**, ảnh SVG/TikZ, dữ liệu biểu đồ và provenance của đúng phiên bản. API yêu cầu owner, không biên dịch TeX hoặc tải tài nguyên ngoài. Citation metadata được snapshot cho bản mới; bản cũ dùng dữ liệu citation đã lưu.
- ZIP dùng class chính thức `IEEEtran` / `acmart`; biên dịch bằng XeLaTeX trên TeX Live/Overleaf. Đây chưa phải dịch vụ xuất PDF tự động trong backend. Mẫu đích cuối cùng vẫn phải theo hướng dẫn cụ thể của hội nghị/tạp chí; không thêm DOI, tác giả hay thông tin chấp nhận giả.

Nguồn mẫu: [IEEE Authoring Tools and Templates](https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/), [ACM Proceedings Template](https://www.acm.org/publications/proceedings-template). Tiêu chí minh bạch về giới hạn, baseline, dữ liệu và tái lập tham khảo [NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist); áp dụng checklist không đồng nghĩa bài đã được chấp nhận.
