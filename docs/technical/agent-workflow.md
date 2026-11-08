# Agent Workflow — vai trò, điều phối và kiểm tra

**Thiết kế gốc:** 09/10/2026; bổ sung cơ chế tiếp tục và phục hồi ngày 06/11/2026 ở mục 10. Xem [SRS](../requirements/SRS.md), [System Design](../architecture/system-design.md), [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md).

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

Đây là nhận xét lịch sử ngày 08/10, không phải trạng thái code ngày 29/10. Các sửa sau đó và bằng chứng hiện tại được tổng hợp tại [Roadmap](../project/roadmap-and-progress.md). Runtime cũ ghi tại [Baseline](../project/baseline-verification.md); đo ích lợi của multi-agent theo [Evaluation Plan](../project/evaluation-plan.md).

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

`search_activity` ghi từng provider/query với trạng thái thành công, lỗi hoặc chưa cấu hình; giữ truy vấn chính xác, thời điểm, tham số, số ứng viên, bản trùng, nguồn tải được và nguồn nhận vào corpus. OpenAlex/Crossref là truy vấn chỉ mục học thuật; Tavily vẫn là web search dù lọc miền học thuật. Truy vấn dự kiến không được biến thành nhật ký thực hiện. Không tự thêm ngày giới hạn xuất bản hay số bài sàng lọc nếu chưa thực hiện. REVIEW hiện là narrative review, chưa thực hiện protocol tổng quan hệ thống/PRISMA hoặc truy vấn trực tiếp Scopus/PubMed/IEEE Xplore.

Tìm nguồn ưu tiên OpenAlex/Crossref, gộp theo DOI rồi tiêu đề chuẩn hóa và URL, giữ metadata thật (tác giả, năm, DOI, venue). Crossref bổ sung metadata khi có record khớp DOI/tiêu đề; hiện chưa có lookup DOI riêng cho mọi nguồn web. Mỗi query lấy tối đa 8 record/index; Tavily lấy 5 URL/query; số nguồn nhận vào vẫn theo `max_sources`. Fetch giới hạn tối đa hai lần số chỗ còn lại (tối thiểu 5), concurrency 5, qua SSRF guard và parser PDF sẵn có. Các cap này là giới hạn tài nguyên, không chứng minh độ bao phủ tài liệu.

Nguồn phân biệt `FULL_TEXT` (PDF do provider công bố), `ABSTRACT` (chỉ dùng abstract từ index sau khi fetch thất bại), `LANDING_PAGE` (trang giới thiệu bài), và `WEB_PAGE`. Writer/Critic nhận phạm vi văn bản này; không được suy chi tiết phương pháp/toàn văn từ abstract. Metadata đi cùng claim, bibliography snapshot, revision và publication export. Nguồn cũ có trường mới null; không sửa ngầm báo cáo đã phát hành.

`OPENALEX_API_KEY` và `CROSSREF_MAILTO` tùy chọn; timeout mặc định 20 giây. `TAVILY_ACADEMIC_DOMAINS` mặc định rỗng, bật sẽ thêm một truy vấn Tavily/domain group cho mỗi query; `advanced` đặt mức dự trù Tavily gấp đôi `basic`. API học thuật qua kiểm tra task/attempt và reservation; Crossref/cuộc gọi miễn phí giải phóng reservation, OpenAlex có key dùng chi phí dự trù `SCHOLARLY_REQUEST_COST_USD` (không phải hóa đơn thực). Rate limit hoặc metadata thiếu được ghi nhận, không tự tạo nguồn thay thế. Tham khảo API: [OpenAlex](https://help.openalex.org/api/), [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [Tavily](https://docs.tavily.com/documentation/api-reference/endpoint/search).

Writer/Critic được yêu cầu giữ riêng giả định/định lý, giả thuyết thiết kế và kết quả thực nghiệm; định nghĩa fairness và giải thích tác động của việc biến đổi input. Đây là hướng dẫn kiểm tra ngữ nghĩa bằng LLM, chưa phải bộ chứng minh toán học. Thực nghiệm Gale–Shapley/NSGA-III, systematic screening và đánh giá độ bao phủ trên bộ benchmark là các hạng mục riêng cần hoàn thiện sau.

Critic kiểm toàn bộ bài cùng contract, provenance và các phát hiện từ bộ kiểm tra xác định. Thiếu tiêu đề/phần bắt buộc, phần rỗng, sai thứ tự, văn bản thiên về liệt kê hoặc dấu hiệu tự nhận phương pháp không có hồ sơ phải quay về Writer trong giới hạn hai vòng sửa. Trước khi giao bài, PostProcessor kiểm tra lại độc lập; lỗi còn tồn tại buộc `NEEDS_REVIEW`, dù LLM trả PASS. Bản cũ vẫn giữ kết quả review theo chính sách đã dùng khi tạo; khi tạo phiên bản mới thì áp dụng contract mới.

Contract mới có `evidence_review_policy` v1: mỗi đoạn có claim marker và đoạn diễn giải trong Discussion/Conclusion được gán identity ổn định. Critic nhận bằng chứng theo đúng claim được trích trong đoạn; bỏ giới hạn lấy 50 claim đầu của bài đối với chính sách này. Đoạn diễn giải không trích nguồn được đối chiếu với các claim đã dùng trong bài và kết quả thực nghiệm được cung cấp. Không có bằng chứng để đối chiếu phải đánh giá là thiếu/không xác minh được, không tự bổ sung kiến thức bên ngoài.

Mỗi batch tối đa 16 đoạn và 24 evidence records, mỗi đoạn tối đa 4.000 ký tự. Vượt giới hạn được ghi thiếu coverage và chặn PASS; không được coi phần bị cắt là đã kiểm tra. Critic trả `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, `CONTRADICTED` hoặc `UNVERIFIABLE`, kèm lý do cho từng đoạn. Nhận xét thiếu, identity lạ/trùng hoặc evidence thiếu quote chuyển `NEEDS_REVIEW`; partial/unsupported/contradicted yêu cầu Writer sửa trong micro-loop đã giới hạn. Không tự coi nhận xét của LLM là chứng minh khoa học.

`evidence_support_review` lưu số đoạn kỳ vọng/đã kiểm, judgments, coverage và hash bản nháp trong metadata phiên bản. PostProcessor chỉ chấp nhận audit đầy đủ, hỗ trợ kết luận và khớp hash bản nháp hiện tại; audit cũ không dùng lại cho bài đã sửa. Contract lịch sử không có policy giữ chế độ cũ. Provider response tối đa 2.048 output tokens/batch cho policy mới, vẫn qua budget guard, không thêm một agent hoặc lượt LLM riêng.

Sau ca review tuyển dụng ngày 30/10/2026, contract mới dùng evidence policy v2 và research-quality policy v1. Collector chia lượt theo discovery query cả trước và sau fetch để các kết quả truy vấn đầu không chiếm toàn bộ cap. Query provenance được lưu trong source và giữ khi restart; nguồn trùng giữ các query đã tìm thấy nó. Coverage này chỉ là proxy theo truy vấn, chưa chứng minh độ liên quan hay bao phủ chủ đề. Thiếu query có log thực thì Critic yêu cầu tìm bổ sung khi còn chỗ; hết cap phải `NEEDS_REVIEW`. Không tăng cap hoặc tạo thêm trích dẫn để làm đủ số lượng.

Writer nhận một citation identity cho mỗi cặp nguồn/quote chuẩn hóa, đồng thời giữ các luận điểm khác nhau rút từ quote đó. Các claim/evidence đã lưu không bị xóa; số quote khác nhau không được gọi là số nghiên cứu độc lập. Marker trùng liên tiếp được gộp và metadata nguồn giải mã HTML entities khi hiển thị. `FULL_TEXT` mới chỉ được gán sau khi scraper xác nhận response là PDF và parser đọc thành công; URL được provider gọi là PDF chưa đủ chứng minh đã đọc toàn văn.

Policy v2 rà cả văn xuôi không có citation và bảng có claim; bỏ Keywords và nhật ký do code tạo khỏi đánh giá ngữ nghĩa. Batch giới hạn 2.600 ký tự hoặc 12 đoạn (đoạn dài đơn lẻ vẫn chịu gate context 4.000 ký tự), tối đa 24 evidence records. Reviewer phải nêu supporting claim IDs hợp lệ và kiểm điều kiện áp dụng khi đánh giá các khẳng định mạnh. Quy tắc xác định yêu cầu ngữ cảnh toàn văn cho khẳng định mạnh về guarantee/Pareto-optimality/robustness; nếu chỉ có abstract/landing page thì yêu cầu viết yếu hơn hoặc bổ sung ngữ cảnh, dù model trả `SUPPORTED`. Đây là hàng rào thận trọng, có thể yêu cầu rà thủ công cho nhận định đúng; không phải bộ chứng minh định lý hay bằng chứng hiệu quả reviewer trên mọi lĩnh vực.

Nhật ký truy vấn thực được code chèn vào mục Literature Search and Scope của REVIEW, gồm provider/query/thời điểm/filter/status/số ứng viên, trùng, fetch và accepted. Giữ nguyên hình trong mục này, không tự sinh số bài screening. API học thuật có concurrency giới hạn (OpenAlex 3, Crossref 2); lỗi ghi HTTP status, retry một lần cho 429/502/503/504 với reservation riêng. Lỗi khác được giữ nguyên, không retry vô hạn. Mô phỏng phát lại bài cũ và unit tests xác nhận các gate kỹ thuật; chưa thay cho benchmark ngữ nghĩa trên bộ bài độc lập hoặc kết quả do chuyên gia chấm.

Kiểm tra cấu trúc và heuristic phương pháp không chứng nhận độ đúng khoa học, độ tin cậy của nguồn hoặc phát hiện mọi cách diễn đạt sai. Critic vẫn là đánh giá nội bộ; người nghiên cứu cần rà soát phương pháp, bằng chứng và yêu cầu nơi dự định nộp. Nguyên tắc tham khảo: [ICMJE manuscript preparation](https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html) và [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020-checklist).

### Hình, số liệu và mẫu trình bày

- Sơ đồ xử lý bằng chứng được ghi rõ là hình khái niệm. Biểu đồ MAE chỉ được tạo khi routine đã chạy thành công và có cả baseline/model; giá trị, số hàng test và provenance được đóng băng cùng phiên bản. Không để LLM tự vẽ số liệu.
- Writer phải giải thích từng Figure trong văn bản, dùng caption và marker tài sản do hệ thống cấp. Kiểm tra trước giao bài bắt hình thiếu/không giải thích, một số số liệu MAE sai, claim vượt trội hoặc ý nghĩa thống kê không có hồ sơ. Kiểm tra tái lập cùng seed không chứng minh ý nghĩa thống kê hay khả năng khái quát.
- Người dùng có thể chọn **IEEE Conference** hoặc **ACM SIGCONF** và tải **ZIP nguồn LaTeX**, ảnh SVG/TikZ, dữ liệu biểu đồ và provenance của đúng phiên bản. API yêu cầu owner, không biên dịch TeX hoặc tải tài nguyên ngoài. Citation metadata được snapshot cho bản mới; bản cũ dùng dữ liệu citation đã lưu.
- ZIP dùng class chính thức `IEEEtran` / `acmart`; biên dịch bằng XeLaTeX trên TeX Live/Overleaf. Đây chưa phải dịch vụ xuất PDF tự động trong backend. Mẫu đích cuối cùng vẫn phải theo hướng dẫn cụ thể của hội nghị/tạp chí; không thêm DOI, tác giả hay thông tin chấp nhận giả.

Nguồn mẫu: [IEEE Authoring Tools and Templates](https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/), [ACM Proceedings Template](https://www.acm.org/publications/proceedings-template). Tiêu chí minh bạch về giới hạn, baseline, dữ liệu và tái lập tham khảo [NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist); áp dụng checklist không đồng nghĩa bài đã được chấp nhận.

## 8. Chỉnh sửa bản thảo theo phiên bản — #65

Người dùng chọn bản thảo và yêu cầu sửa cách trình bày tại `/research/{id}/revisions`. Chỉ bản mới nhất được làm base cho yêu cầu mới; bản cũ vẫn xem, hỏi và xuất được. API GET/POST `/research/{id}/report/versions/{n}/revisions` yêu cầu owner, có request UUID chống gửi lặp, lịch sử phân trang và `private, no-store`. Mỗi bài chỉ có một request sửa active, tối đa 30 request. Thay đổi dữ liệu/phương pháp phải tạo lượt nghiên cứu mới.

Luồng thực hiện: **lưu request và outbox cùng transaction → worker claim/lease → Writer → Critic và micro revision hữu hạn → PostProcessor/validator → version mới**. Entry editorial bỏ qua Supervisor/search/ingestion/Analyst/runner; macro loop có giới hạn 0 nên không tự tìm thêm bằng chứng. Thiếu bằng chứng thì giao bản cần rà soát, không tự dựng Results. Dùng ngân sách còn lại của bài, không reset cap/usage để sửa tiếp.

Nguồn/claims/chunks chỉ được lấy từ Citation của đúng base version, kiểm lại chuỗi cùng task và quote nguyên văn. Bibliography metadata, contract và provenance giữ theo bản gốc; nhãn thư mục được khôi phục về claim markers để Writer tiếp tục dùng validator. Nhãn cùng source có thể ứng với nhiều claims của bản gốc; kiểm lineage không tự chứng minh diễn giải câu văn mới đúng về ngữ nghĩa.

Các bản mới lưu `manuscript_input_snapshot` (plan, protocol, dữ liệu thực địa đã cung cấp, kết quả phân tích; không lưu lại CSV thô trong snapshot). Bản REVIEW lịch sử có contract và citations hợp lệ có thể sửa; bản tính toán cần frozen completed analysis; bản human-led cần frozen fieldwork input. Thiếu snapshot thì trả 409 và yêu cầu lượt research mới, không lấy dữ liệu hiện tại để điền ngược cho bài cũ. Sửa bài không ghi lại AnalysisRun/journal hay chạy lại routine.

Checkpoint và request giữ workflow identity qua redelivery. Trước publish, worker kiểm task/attempt/lease và base vẫn là bản mới nhất, rồi lưu version/citations/request result cùng transaction. Hủy, xóa, hết budget hoặc mất base fence không được ghi đè version cũ. Version xuất bản mới có provenance nối về request và base version; PASSED vẫn chỉ là kiểm tra nội bộ.

## 9. Cách viết và trình bày học thuật — contract v3 (#69)

Các lượt nghiên cứu mới lưu thêm `writing_brief` cùng contract. Writer và Critic đọc cùng mục tiêu cho từng phần, theo đúng loại nghiên cứu; brief là hướng dẫn biên tập, không phải dữ liệu nghiên cứu và không cấp thêm nguồn để trích dẫn. Bản đã lưu giữ contract cũ. Các ngưỡng kiểm tra xác định và Critic nội bộ vẫn không thay thế đánh giá học thuật của người nghiên cứu.

| Nội dung | Áp dụng trong sản phẩm |
|---|---|
| Lập luận | Introduction dẫn tới RQ/gap có nguồn; đoạn phân tích nối luận điểm, bằng chứng và lý giải, nêu giả định/giới hạn. Related Work so sánh theo chiều chung, không liệt kê từng paper. Discussion trả lời RQ, xem xét phản chứng và giải thích thay thế |
| Tổng quan | Tổng hợp theo chủ đề/câu hỏi, chỉ mô tả tìm kiếm thực sự đã ghi; kết luận là tổng hợp giới hạn. Không tự chuyển thành systematic review hay thêm số liệu PRISMA |
| Tính toán | Methods/setup mô tả routine, dữ liệu, split/seed/baseline/metrics đã có; Results giữ cả kết quả âm. Không suy ý nghĩa thống kê từ một split hoặc một lần kiểm lặp |
| Nghiên cứu ngoài hệ thống | Phân biệt protocol với nghiên cứu đã thực hiện; quy nguồn kết quả cho dữ liệu người dùng. Không tự thêm người tham gia, phê duyệt đạo đức hoặc kiểm định chưa chạy |
| Figure | Style mới có trục MAE bắt đầu từ 0, vạch chia, giá trị trực tiếp và giới hạn single-split; sơ đồ là khái niệm xử lý bằng chứng. Có SVG title/description và ACM Description. Hình lặp/sai thứ tự phải sửa; không suy error bars từ một kết quả |
| Bảng | Caption riêng dạng `Table N. ...` ngay trước bảng được giữ khi xuất LaTeX; văn xuôi phải giải thích ý nghĩa và provenance, tránh dùng bảng và hình trùng lặp không cần thiết |
| Reference | IEEE giữ tác giả/năm khi có; nguồn author-date trùng nhãn có hậu tố a/b, vẫn giữ các claim links. Thiếu metadata được ghi trong review metadata/provenance; không tự bịa DOI, venue, tác giả hay ngày truy cập. ZIP có `references.json` để người nghiên cứu đối chiếu |
| Phiên bản | `figure_style_version` nằm trong scientific context của bản mới; export bản lịch sử vẫn dựng theo style cũ. Nhãn author-date lịch sử mơ hồ phải báo lỗi thay vì âm thầm trỏ sang nguồn khác |

Định dạng author-date hiện dùng trường tác giả chưa tách cấu trúc và hậu tố theo thứ tự trích dẫn; chưa phải bộ máy chuẩn hóa đầy đủ mọi quy tắc APA/Harvard. Bản mới cải thiện tính phân biệt nguồn, không chứng nhận reference đã đủ điều kiện nộp mọi venue. Các trường metadata thiếu phải được kiểm tra với nguồn gốc trước khi nộp.

### Nguồn học cách viết và trình bày

| Nguồn chính thống / bài nghiên cứu | Nguyên tắc rút ra, không sao chép nội dung |
|---|---|
| [IEEE: Structure Your Article](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/structure-your-article/) | Chức năng của Abstract/Introduction/Methods/Results/Discussion; phương pháp có thể tái lập, kết luận tương xứng bằng chứng và chỉ dẫn nguồn trực tiếp liên quan |
| [Scientific Reports: submission guidelines](https://www.nature.com/srep/author-instructions/submission-guidelines) | Cấu trúc tùy loại bài/venue; caption, đơn vị và mô tả xử lý thống kê; không dùng hình lấy từ web khi chưa có quyền phù hợp |
| [ACM SIGACCESS: Describing Figures](https://www.sigaccess.org/welcome-to-sigaccess/resources/describing-figures/) | Mô tả cấu trúc/giá trị quan trọng, trục và xu hướng; không phụ thuộc màu hoặc lặp nguyên caption |
| [Shao et al., STORM, NAACL 2024](https://aclanthology.org/2024.naacl-long.347/) | Học cách nối vấn đề với phương pháp, hình tổng quan và đánh giá; tách đóng góp khỏi hạn chế. Đây là bài mô tả hệ thống sinh nội dung Wikipedia, không phải bằng chứng hệ thống tự viết nghiên cứu mới |
| [Bergstra & Bengio, JMLR 2012](https://www.jmlr.org/papers/v13/bergstra12a.html) | Học cách định nghĩa bài toán/giả định, so sánh trong ngân sách cụ thể và giới hạn kết luận theo tập dữ liệu; không mượn số liệu hoặc kết luận ưu thế cho Synthia |
| [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020-checklist) | Phân biệt yêu cầu của tổng quan hệ thống với tổng quan phân tích hiện hỗ trợ; không dùng checklist làm chứng nhận tuân thủ |

Chỉ học cấu trúc lập luận và nguyên tắc thiết kế hình. Không sao chép câu văn, ảnh, caption, bibliography hoặc số liệu của các bài mẫu vào bài của người dùng. Chỉ nguồn nằm trong evidence của đúng lượt nghiên cứu mới được trở thành citation. Những quy tắc này không đòi mọi lĩnh vực có cùng khung IMRaD hay mọi bài phải có biểu đồ thực nghiệm.

### 9.1. Bố cục phân cấp và lập luận — contract v4, 02/11/2026 (#84)

Code c72e936 / PR #85 có 118 ca focused, 513 backend tests, 20 frontend tests và 5/5 CI đạt. Đây là nghiệm thu cơ chế viết/kiểm phần mềm; chưa có đánh giá chất lượng bài thật sau sửa. Phần bổ sung word/output profile dùng chung Writer/baseline có 121 focused tests đạt; CI của head cuối tại PR #85 là cổng nghiệm thu phiên bản mới nhất.

Kế hoạch nghiên cứu mới có `section_outline`: mục cha, các mục nhỏ theo câu hỏi/chủ đề và mục đích lập luận. Supervisor đề xuất ngay trong lần lập kế hoạch hiện có, không mở một vòng gọi model mới. Đây là đề cương dự kiến trước tìm nguồn, không phải kết quả nghiên cứu. Writer phải điều chỉnh theo bằng chứng thực có; không tạo số liệu hoặc suy luận không được hỗ trợ để lấp đầy đề cương. H2 giữ vai trò của từng phần, H3 phát triển các luận điểm/câu hỏi cụ thể; H4 chỉ dùng khi cần bên dưới H3.

| Phần | Cách triển khai trong bài |
|---|---|
| Abstract | Tự đứng được: câu hỏi/mục đích → cách thực sự đã làm → phát hiện/tổng hợp chính có căn cứ → ý nghĩa có giới hạn. Viết phù hợp với phần thân, không thêm số liệu hoặc novelty |
| Introduction | Các đoạn liên kết đi từ bối cảnh → vấn đề và hạn chế nghiên cứu trước có nguồn → gap có giới hạn → RQ → cách tiếp cận/đóng góp thực tế. Không ép năm bước này thành năm tiêu đề nhỏ ngắn, rời rạc |
| Related Work | Đối chiếu theo tiêu chí có ý nghĩa: giả định, phương pháp, dữ liệu/bối cảnh, bằng chứng và hạn chế. Mục nhỏ có thể nêu một dòng phương pháp hoặc một cuộc tranh luận; tránh một mục nhỏ cho mỗi paper |
| REVIEW: phạm vi/phương pháp | Phân biệt cách xác định phạm vi/tìm nguồn thực tế với cách lựa chọn, giới hạn nguồn và tổng hợp. Nhật ký kỹ thuật là thông tin bổ trợ, không thay nội dung phương pháp |
| REVIEW: tổng hợp | Các mục nhỏ được đặt theo câu hỏi, cơ chế, chiều so sánh hoặc bất đồng có bằng chứng; mỗi mục giải thích điểm thống nhất/khác biệt, giả định, hàm ý và điều chưa biết. Không chuyển thành Results của thí nghiệm chưa làm |
| Tính toán: Methods / Setup | Tách định nghĩa bài toán/biến/giả định/routine đã chạy khỏi dữ liệu, preprocessing, split, baseline, cấu hình và metrics. Chi tiết chỉ được đưa vào nếu có trong provenance |
| Tính toán: Results | Mục nhỏ theo RQ hoặc phép so sánh đo được; trình bày baseline và mô hình trên cùng thiết lập, kết quả âm/không kết luận và kiểm lặp thực sự có. Không tạo ablation, uncertainty hay biểu đồ mới khi chưa thực hiện |
| Dữ liệu người dùng: Methods / Results | Tách thiết kế/nguồn dữ liệu/mẫu khỏi đo lường, thu thập, phân tích và ethics đã được cung cấp. Kết quả tổ chức theo câu hỏi/chủ đề/outcome thực có, ghi rõ phần do người dùng báo cáo và phần hệ thống thực sự phân tích |
| Discussion | Trả lời RQ từ bằng chứng; giải thích cơ chế hoặc cách hiểu có điều kiện, so với nghiên cứu trước, xem xét giải thích thay thế và khả năng áp dụng. Không chỉ lặp Results |
| Limitations / Conclusion | Nêu giới hạn cụ thể làm yếu kết luận nào; kết luận quay lại câu hỏi với mức khẳng định tương xứng. Không thêm bằng chứng hoặc đề xuất chưa thực nghiệm như kết quả |
| Figure / table / references | Đặt gần luận điểm được minh họa, giải thích trong văn bản, caption có phạm vi/provenance; reference hỗ trợ đúng phát biểu. Gộp nhãn trích dẫn liền nhau của cùng nguồn nhưng giữ đủ claim/evidence links |

Các phần phân tích/phương pháp đủ dài dùng khoảng 2–4 mục H3 có nội dung; bộ kiểm tra chỉ bắt dấu hiệu quan sát được như mục trống, thiếu phân cấp, trùng mục hoặc phân mảnh quá mức. Ngưỡng 350 ký tự/mục cha, 50 ký tự văn xuôi/mục con và tối đa 6 mục con là heuristic sản phẩm, không phải tiêu chuẩn học thuật hoặc chứng nhận viết hay. Mục ngắn không bị ép chia nhỏ. Tiêu đề bài và mục cha có mục con không trở thành đoạn “No section body” gửi Critic; ngữ cảnh mục cha được giữ khi review từng mục con. Code fences không được giả làm đề mục của bài.

Học bố cục từ các ví dụ khác phương pháp: [Ruder, tổng quan các thuật toán gradient descent](https://arxiv.org/html/1609.04747v2) cho cách tổng hợp theo họ phương pháp/đánh đổi; [STORM, NAACL 2024](https://arxiv.org/html/2402.14207v1) cho phân cấp phương pháp, thiết lập và phân tích đánh giá; [Bloom, Han & Liang, Nature 2024](https://www.nature.com/articles/s41586-024-07500-2) cho quan hệ giữa câu hỏi, thiết kế nghiên cứu, kết quả và giới hạn trong nghiên cứu thực nghiệm. Chỉ rút ra vai trò cấu trúc, không nhập kết quả/mẫu/số liệu/citation của các bài đó vào output. [Nature Methods: content types](https://www.nature.com/nmeth/content) cũng cho thấy quy tắc subheading phụ thuộc venue; profile mặc định của Synthia không tự nhận tuân thủ y hệt mọi tạp chí.

Nếu người dùng muốn theo một bài mẫu cụ thể, cần có bài mẫu và xác định cùng loại phương pháp; hiện chưa có chức năng tự trích style/template từ file bài mẫu. Profile mới không được coi là đã đọc một exemplar mà người dùng chưa cung cấp. Bài cũ giữ nguyên contract; sửa phiên bản cũ vẫn giữ policy đã snapshot. Nghiên cứu mới dùng contract v4; evaluation phải freeze `REVIEW-v4` và revision mới, không dùng protocol `REVIEW-v3` cũ để đo code mới.

### 9.2. Context, bằng chứng và giới hạn tài khoản

Context là giới hạn một request; ngân sách token của ResearchTask là giới hạn cộng dồn nhiều request. Free/paid tier chủ yếu cần kiểm qua quota/model access/rate limits của tài khoản, không suy ra context chỉ từ chữ “free”. Tham khảo [Google: tokens/context](https://ai.google.dev/gemini-api/docs/tokens), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) và [pricing/tier](https://ai.google.dev/gemini-api/docs/pricing).

Lượt kiểm tra metadata model ngày 02/11 trả input limit 1.048.576 và output limit 65.536 cho hai model đang cấu hình `gemini-3.5-flash` và `gemini-3.5-flash-lite`; đó không phải xác nhận quota/billing tier hoặc cam kết chất lượng. Contract v3 của lượt đó đặt output SHORT=4096, MEDIUM=8192, LONG=12288. Contract v4 mới đóng băng độ dài SHORT=600–900 từ (cap 8192), MEDIUM=1400–2000 (12288), LONG=2400–3200 (16384); đây là mục tiêu khi đủ bằng chứng, không ép thêm nội dung để đủ từ. Tổng cap của task không tăng; mọi request vẫn phải qua budget guard. Bản lịch sử giữ profile cũ. Bài được audit ngày 02/11 có Writer input 8.014 token, output 2.345, không báo truncated; sau gộp trùng Writer nhận 5 claim/evidence records từ 3 nguồn. Chưa có bằng chứng context overflow trong lượt đó; model không thể tự bổ sung tài liệu mà pipeline chưa đưa vào.

Writer mới ghi số nguồn/quote, kích thước prompt, token dự phòng, output limit, finish reason và model được provider báo khi có; không lưu raw prompt hay secrets vào log. Các số đo này hỗ trợ chẩn đoán thiếu nguồn, mất thông tin khi trích xuất, quota, output truncation và khả năng model riêng biệt. Cải thiện hierarchy chưa chứng minh chất lượng học thuật tốt hơn; cần chạy/chấm bài thật trên các thể loại/chủ đề theo Evaluation Plan. Không tự tăng cap hoặc đổi model để che lỗi pipeline.

### 9.3. Chọn và chuyển bằng chứng — cập nhật 03/11/2026 (#86)

Policy `evidence_selection` v1 tách ba việc: phát hiện tài liệu, chọn đoạn liên quan, và đánh giá mức hỗ trợ của luận điểm. Điểm xếp hạng hay quote khớp không phải chứng nhận chất lượng nghiên cứu.

| Bước | Cách thực hiện | Giới hạn |
|---|---|---|
| Supervisor | Tối đa 5 câu hỏi bằng chứng, gắn với mục bài và vai trò FOUNDATION / CORE_CONCEPT / COMPARISON / LIMITATION / COUNTEREVIDENCE; ưu tiên truy vấn công trình gốc khi phù hợp | Là kế hoạch, không phải kết luận; không tăng budget của task |
| Researcher | Xếp hạng title/abstract rồi đánh giá metadata cho tối đa 24 ứng viên trong một lần gọi model qua budget guard mỗi vòng; ưu tiên nghiên cứu gốc phù hợp câu hỏi, phân biệt review và hướng dẫn thực hành; cân bằng theo need ID được metadata chỉ ra, trước và sau tải nguồn | Hint chỉ được dùng khi DIRECT và thuộc kế hoạch; FOUNDATION cần PRIMARY. Không có hint hợp lệ thì cân bằng truy vấn như trước. Đây chưa phải kiểm chứng nội dung hoặc peer review; ứng viên không chắc vẫn được giữ |
| Curator: nguồn web mới | Lưu tối đa 128 đoạn phân bố từ đầu đến cuối; chỉ nhúng tối đa 8 đoạn đại diện | Corpus được lấy mẫu, không phải toàn bộ paper đã được đọc. Macro loop không tự nhúng tất cả phần text còn lại. Luồng PDF upload giữ chính sách hiện có |
| Retrieval | Kết hợp thứ hạng vector và PostgreSQL full-text bằng reciprocal rank fusion; ưu tiên một đoạn mỗi nguồn trước khi lấy thêm đoạn cùng nguồn | Giữ context 3 đoạn mỗi câu hỏi; source/task phải khớp và ingestion READY. Không có kết quả liên quan thì trả trống, không lấy đoạn đầu bất kỳ. Điểm fused rank không phải cosine distance hay confidence |
| Analyst | Quote nguyên văn, Chunk ID chính xác, điều kiện/giả định cũng là trích đoạn khớp nguồn; tối đa 6 claim mỗi câu hỏi | Quote trùng ở nhiều chunk mà không có identity rõ bị từ chối. Marker mới gắn một cặp claim–evidence cụ thể để không gộp mất nguồn khi hai paper nêu cùng nhận định; lịch sử không bị viết lại. Khớp quote chỉ xác minh provenance, chưa chứng minh entailment |
| Writer / Critic | Nhận ma trận quote candidates và khoảng thiếu; đối chiếu nguồn, nêu giới hạn, không tạo citation cho đủ số lượng | Thiếu quote cho nội dung trung tâm cần tìm thêm hoặc NEEDS_REVIEW. Thiếu nguồn bối cảnh/counterevidence có thể là giới hạn được công khai, không chứng minh không có nghiên cứu trước |

Với line-wrap của PDF/HTML, chỉ cho phép căn chỉnh whitespace để tìm lại **đúng span nguyên văn trong nguồn**, rồi lưu chính span gốc đó. Không sửa chữ, hoa/thường, dấu câu hoặc dấu gạch nối để làm quote khớp. Metadata giữ số claim model đề xuất và số không được giữ, giúp tách lỗi trích xuất khỏi thiếu nguồn; không lưu raw prompt vào log.

Critic nhận cùng ma trận thiếu bằng chứng và các giả định trích từ nguồn. Trường claim là diễn giải do AI sinh, không phải bằng chứng độc lập: phải đối chiếu quote gốc, không dùng title/venue hoặc nội dung bài viết để tự chứng minh luận điểm. Một quote nêu tên các loại lỗi không đủ hỗ trợ định nghĩa chi tiết chưa có trong đoạn; một kết quả triển khai không đủ chứng minh ưu thế tổng quát, statistical significance hoặc baseline chưa đo. Prompt là biện pháp hỗ trợ, chưa bảo đảm reviewer luôn phát hiện sai; audit độc lập và đánh giá người nghiên cứu vẫn cần thiết.

Plan mới dùng `evidence_review_policy` v3: khi đánh giá SUPPORTED và nêu claim hỗ trợ, Critic phải trả quote anchor gồm claim/source/chunk ID và một span nguyên văn từ quote đã cung cấp. Mọi citation trực tiếp trong đoạn phải được đối chiếu; một citation đúng không che được citation khác chưa kiểm. Sai ID, quote bịa hoặc thiếu anchor khiến kiểm tra không hoàn tất và không được tính là đạt. Mô tả phương pháp thực sự đã làm/giới hạn chưa trích nguồn có thể dựa trên provenance, không bị buộc gắn citation không liên quan. Anchor xác nhận đối chiếu nguồn, **không chứng minh entailment**; một reviewer vẫn có thể hiểu sai quote có thật. Plan lịch sử giữ policy đã snapshot, không nâng v2 thành v3 khi resume; formal evaluation phải freeze fingerprint mới.

Policy v4 kế thừa quote anchors và bổ sung fact có kiểu cho **thao tác chia dữ liệu bằng seed đã chạy**. Fact chỉ sinh từ routine được hỗ trợ có trạng thái COMPLETED, manifest hợp lệ và kiểm tra lặp lại PASSED; reviewer phải viện dẫn đúng fact ID. Không đòi một paper bên ngoài để chứng minh seed của chính lần chạy này. Các khẳng định về độ chính xác, ổn định, tối ưu, công bằng, nhân quả, thống kê hay riêng tư không được miễn kiểm nhờ có seed. Trường hợp không chắc vẫn giữ kiểm tra bảo thủ; lịch sử v1–v3 giữ nguyên policy cũ.

`revision_policy` v2 sửa cách tính lượt: một bản nháp ban đầu cộng tối đa đúng hai lượt sửa khi cấu hình là 2. Nếu đã xác định được lỗi văn bản và vẫn thiếu nguồn trung tâm, có thể thực hiện lượt sửa để thu hẹp kết luận/nêu giới hạn; không được dùng lượt sửa để tự tạo bằng chứng. Gate nguồn vẫn kiểm lại trước phát hành. Reviewer yêu cầu người kiểm tra, lineage sai, bản sửa không đổi, hết lượt hoặc hết budget đều có điều kiện dừng riêng; không ép thành COMPLETED. Contract lịch sử chưa có policy này giữ cách định tuyến trước đây.

### 9.4. Provider được đóng băng cho đánh giá đối chứng

Evaluation executor chọn `controls.provider` rõ ràng (`openai` hoặc `gemini`), không dùng chuỗi fallback của ứng dụng. Cả hai adapter tắt cache và retry tự động, giữ raw response/usage để Meter reserve và đối chiếu từng attempt; source corpus không gọi web/embedding bên ngoài. Gemini structured output dùng wire schema tương thích nhưng vẫn kiểm lại bằng schema đầy đủ tại local. Dry plan không khởi tạo client hoặc gọi provider.

Đối với model không nhận điều chỉnh sampling, protocol phải ghi `sampling_mode=provider_default` và `temperature=null`, không ghi một giá trị temperature như thể đã áp dụng. Ví dụ Gemini 3.5 Flash-Lite đang có hành vi này theo [thay đổi API của Google](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6); raw metadata còn cần ghi model revision có/không quan sát được. Chọn cùng model ID không chứng minh nhà cung cấp giữ nguyên weights giữa mọi thời điểm.

Ngày 03/11/2026, giá standard text của Gemini 3.5 Flash-Lite được đối chiếu tại [bảng giá chính thức](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite): 0,30 USD/triệu input token và 2,50 USD/triệu output token, bao gồm thinking. Ước tính model này trong ứng dụng được cập nhật; số lịch sử giữ nguyên cách tính đã ghi, không sửa thành hóa đơn. Bảng giá model khác còn có giá trị legacy, cần rà soát riêng trước triển khai trả phí rộng. Meter đánh giá dùng mức giá đã freeze và trần campaign riêng; không suy tài khoản đang free hay paid chỉ từ API key.

Coverage được snapshot vào metadata phiên bản bài báo. Giao diện gọi các claim là **Source-linked Claims**, Critic là **AI Critique**; không gọi đó là peer review độc lập. Baseline đánh giá cũng được cấp Chunk ID để không bị bất lợi khi quote chung xuất hiện ở nhiều nguồn. Executor vẫn dùng corpus/retrieval profile đã freeze riêng cho cả ba arm; fingerprint toàn bộ code thay đổi nên phải freeze revision mới trước khi đánh giá trả phí. Không suy từ regression fixtures sang kết luận multi-agent tốt hơn baseline.

Tham khảo kỹ thuật: [PostgreSQL full-text ranking](https://www.postgresql.org/docs/16/textsearch-controls.html), [pgvector hybrid search](https://github.com/pgvector/pgvector#hybrid-search). Không đổi embedding model hoặc vector format trong policy này; đổi profile cần kế hoạch re-index riêng, không trộn embedding spaces của corpus lịch sử.
### Shared Gemini request pacing

The application LLM factory coordinates Gemini calls through Redis using an atomic server-time reservation for each configured API key and model. `GEMINI_REQUESTS_PER_MINUTE` defaults to 12; `GEMINI_MAX_QUEUE_SECONDS` bounds total waiting at 90 seconds. Set the rate to the actual project quota, allowing for requests made outside this application. This limits request bursts; it does not guarantee remaining daily/token quota or provider availability.

Waiting happens before the provider budget reservation. A full queue makes no provider request. A 429 records a bounded shared cooldown; requests already waiting re-reserve spaced slots instead of all waking together. There is no hidden same-provider retry. Cancellation and task budget checks still run before the actual request. Redis errors fail closed. The frozen evaluation transport is separate; the earlier pilot's rate-limit failures remain recorded and are not retrospectively repaired.

## 10. Tiếp tục sau lỗi và giới hạn provider — 06/11/2026

**Retry không đặt lại bài.** Endpoint retry tiếp tục checkpoint của workflow hiện có, giữ nguồn, artifacts, lịch sử và ledger. Nút workspace là **Continue from failed step**; tải lại report là thao tác đọc riêng. Bài chạm giới hạn bị chặn trước khi tạo job. Với thiếu token, người dùng có thể xem và chủ động chọn tăng rồi tiếp tục cùng bài. Không tự tăng cap hoặc xóa usage khi đổi model.

Ngày 08/11, `POST /research/{id}/retry` nhận optional body gồm hai trần token mới. Request không có body giữ hành vi retry thông thường; body chỉ cho tăng, không cho giảm, sửa ledger hoặc thay trần tiền/lượt/thời gian. Mặc định 100.000 input/50.000 output, trần tuyệt đối 300.000/200.000. Chỉ nhận FAILED hoặc NEEDS_REVIEW do BUDGET_LIMIT, khóa task/run thuộc owner, giữ thread, ghi audit thay đổi, tái dùng outbox và commit một giao dịch. Retry trùng khi QUEUED bị từ chối; hết trần khác thì rollback cả thay đổi. Kiểm thử checkpoint PostgreSQL xác nhận bước tìm nguồn không chạy lại sau khi nâng token. Không có bảo đảm provider sẽ đáp ứng hoặc hạn mức thời gian/lượt còn đủ để hoàn tất.

### 10.1. Chờ dịch vụ mà không giữ worker

429 được phân loại từ HTTP status/metadata đã nhận: giới hạn ngày, upstream tạm thời, tốc độ hoặc chưa xác định. Chỉ tạm hoãn khi có tín hiệu retry phù hợp, tối đa hai lần trong cùng workflow và tối đa 300 giây mỗi lần. Checkpoint và `run_id` giữ nguyên; task về QUEUED, worker lease và đồng hồ active được nhả; outbox có `available_at` để dispatcher đánh thức sau. Delivery sớm không chạy workflow. Daily limit hoặc thời gian chờ không phù hợp cần quyết định người dùng. Raw response/key không được công bố.

### 10.2. Đầu ra có cấu trúc và lỗi phân tích

BYOK dùng JSON Schema khi người dùng chọn khả năng này và schema có thể đóng các object keys an toàn. Schema chứa dictionary động dùng JSON object để không mất biến nghiên cứu; cả hai đều được Pydantic kiểm đầy đủ. JSON không hợp lệ có tối đa một correction pass; output bị cắt không được sửa đoán. Mỗi attempt đều reserve/reconcile ngân sách. Một extraction hợp lệ rỗng nghĩa là chưa có bằng chứng hỗ trợ; lỗi provider không được biến thành extraction rỗng rồi tiếp tục tiêu hết ngân sách ở các câu hỏi khác.

### 10.3. Lưu đơn vị đã hoàn tất

`provider_results` lưu JSON đã kiểm tra và các nhóm Writer hoàn chỉnh, riêng cho task/workflow. Fingerprint bao gồm input, schema, model, giới hạn và cấu hình kết nối; không lưu key trong payload. Đọc/ghi kiểm owner, trạng thái task/run, attempt và lease; hủy hoặc delivery cũ không được ghi thêm. Một kết quả khớp dùng lại không tạo call hay usage mới. Thay input/config tạo fingerprint khác. Đây không phải bảo đảm exactly-once với provider: nếu tiến trình chết trước khi lưu phản hồi thì lần sau có thể cần gọi lại.

Với kết nối cá nhân và độ dài MEDIUM/LONG, Writer bắt đầu bằng nhóm phần, không tiêu trước một lượt toàn bài dễ timeout. Các trường hợp khác thử bản đầy đủ và chuyển sang nhóm khi provider timeout/cắt. Abstract viết sau cùng nhưng lắp theo thứ tự contract. Các nhóm có cấu trúc dùng H2 trong tập heading được yêu cầu và các trường `heading/body/subsections` riêng; renderer sở hữu xuống dòng và H3. Body không chứa heading Markdown lẫn nội dung. Mỗi nhóm phải đúng thứ tự và đủ nội dung trước khi lưu. Retry giữ chiến lược và bỏ qua nhóm đã hoàn tất. Chưa đủ nhóm thì báo `MANUSCRIPT_INCOMPLETE`; không ghép đoạn bị cắt thành bài hoàn chỉnh. References vẫn được tạo từ lineage đã lưu. Tiến độ UI chỉ công bố số nhóm hoàn tất/tổng nhóm, không tiết lộ chain-of-thought.

Ngày 08/11, Methodologist chuyển sang `MethodologistPlan`: chỉ sinh các trường câu hỏi, giả thuyết, biến, thiết kế, thu thập, phân tích và đạo đức một lần. Renderer xác định tạo `protocol_markdown` từ chính các trường đó, giữ shape lưu trữ/resume cũ. Giả thuyết rỗng vẫn hợp lệ với nghiên cứu mô tả. Đây là giảm đầu ra lặp, không tự xác nhận phương pháp có giá trị khoa học.

Transport của biến dùng danh sách object đóng `{role, names}` để có thể yêu cầu JSON Schema; sau khi kiểm hợp lệ mới chuyển sang dictionary đã lưu của protocol. Schema đóng không có nghĩa nhà cung cấp chắc chắn trả đúng: vẫn kiểm Pydantic và giới hạn correction pass. Catalog giữ khả năng structured output do provider công bố, kể cả router; log lỗi schema chỉ ghi tên schema/field/type đã biết, không ghi raw response hoặc dữ liệu người dùng.

Rendering policy v2 chỉ áp dụng kế hoạch mới: routine `tabular_regression_v1` COMPLETED có đủ MAE/RMSE/R² hữu hạn được dựng bảng so sánh từ metrics, chèn một lần trong Results. Không tạo số khi thiếu run/metrics, không đổi policy của plan lịch sử. Writer được yêu cầu giải thích bảng và dùng đúng hình hai cột MAE. Validator báo tham chiếu bảng không có bảng thật, trùng số bảng và một số cách diễn giải sai hình như per-observation/residual plot. Quy tắc ngôn ngữ là bộ lọc giới hạn, không phải xác minh ngữ nghĩa toàn diện.

Contract v6 thêm `study_provenance_policy` cho bài mới. Kiểm tra biên tập đối chiếu tuyên bố điều chỉnh/kiểm định công cụ đo với `method_notes`/`data_provenance` do người nghiên cứu cung cấp; tài liệu đã trích và protocol đề xuất không xác nhận công việc đã làm trong nghiên cứu này. Phát hiện bước đầu các khẳng định không có nghiên cứu trước/đầu tiên vượt phạm vi corpus; phân biệt mô tả phủ định, đề xuất tương lai và nghiên cứu trước. Rules tiếng Anh/Việt là bộ lọc bảo thủ, không phải kiểm chứng ngữ nghĩa đa ngôn ngữ toàn diện. Contract lịch sử giữ nguyên chính sách cũ. Writer/Critic nhận hướng dẫn tương ứng; user provenance vẫn là khai báo cần người nghiên cứu chịu trách nhiệm.

Các cơ chế trên có kiểm thử lỗi, hủy, lặp delivery, cấu hình đổi và ba loại bài. Chúng giảm công việc lặp, không bảo đảm provider miễn phí luôn còn quota hoặc manuscript đạt chất lượng xuất bản.
