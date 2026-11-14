# Câu hỏi và trả lời khi bảo vệ Synthia

Tài liệu giúp Nguyễn Đình Chiến chuẩn bị trả lời câu hỏi về bài toán, tính năng, công nghệ, kiến trúc, kiểm thử và hướng phát triển. Câu trả lời mẫu viết để có thể nói trực tiếp.

**Quy tắc:** phân biệt tính năng đã có với đề xuất tương lai; chỉ nêu test/release evidence đúng revision; nói rõ giới hạn. Không tuyên bố “đạt Q1”, “production-ready”, “hết hallucination” hay “multi-agent luôn tốt hơn” khi chưa có bằng chứng.

## 1. Đề tài và bài toán

### Synthia giải quyết vấn đề gì?

**Trả lời:** Synthia hỗ trợ tổ chức quy trình từ câu hỏi nghiên cứu đến bản thảo có thể đối chiếu nguồn, bằng chứng, kết quả và tiến trình. Nghiên cứu không chỉ là viết văn bản: còn phải tìm tài liệu, tổng hợp bằng chứng, chọn phương pháp, thực hiện hoặc thu thập dữ liệu, và kiểm tra kết luận. Một câu lệnh đơn lẻ thường không giúp theo dõi tất cả các bước đó thành hồ sơ thống nhất.

### Ai là người dùng? Đầu ra là gì?

Người học, sinh viên và nhà nghiên cứu cần hỗ trợ quy trình. Đầu ra là bản thảo theo loại nghiên cứu cùng hồ sơ nguồn, bằng chứng, kết quả tính toán hoặc protocol khi phù hợp. Đây là bản hỗ trợ để con người kiểm tra và hoàn thiện, không phải bài đã bình duyệt, được tạp chí chấp nhận hay đảm bảo đúng mẫu của một venue cụ thể.

### Vì sao có ba luồng nghiên cứu?

Ba luồng phản ánh ba cách lấy bằng chứng mà bản demo hỗ trợ: **tổng quan** dựa trên tài liệu đã công bố; **thực nghiệm tính toán** chạy routine được hỗ trợ trên dữ liệu; **nghiên cứu ngoài hệ thống** cần người dùng làm khảo sát/lab/thực địa rồi nạp dữ liệu. Đây là các luồng chính của sản phẩm, không phải phân loại đầy đủ mọi phương pháp khoa học.

### Hệ thống tự làm khảo sát/lab được không?

Không. Hệ thống có thể giúp chuẩn bị protocol, dừng chờ dữ liệu, nhận dữ liệu và hỗ trợ viết sau đó. Con người vẫn chịu trách nhiệm tuyển người, xin phê duyệt đạo đức khi cần, thực hiện khảo sát/lab và khai báo dữ liệu trung thực.

### Đây có phải chỉ là prompt engineering? Có huấn luyện model không?

Không huấn luyện hoặc fine-tune foundation model. Prompt là một phần; dự án còn có giao diện/API, hàng đợi, workflow/state, tìm và lưu nguồn, phân tích bằng chứng, runner, quản lý hạn mức, kiểm tra citation, checkpoint và monitor. Model bên ngoài được dùng để suy luận; chất lượng phụ thuộc model, dữ liệu, công cụ và đánh giá.

### Đóng góp mới là gì? Có hơn chatbot hoặc sản phẩm khác không?

Đây là đồ án thiết kế và tích hợp workflow hỗ trợ nghiên cứu có phân vai, nhánh theo cách tạo bằng chứng, trạng thái bền vững, dừng/tiếp tục và liên kết nguồn/kết quả với bản thảo. Chưa có benchmark đối chứng để tuyên bố Synthia tốt hơn chatbot, single-agent hay sản phẩm nghiên cứu khác.

## 2. Tính năng và cách sử dụng

### Người dùng đi qua ứng dụng theo thứ tự nào?

1. Đăng nhập → **Dashboard** để xem các bài và trạng thái.
2. **Tạo bài nghiên cứu mới** → nhập câu hỏi, chọn loại nghiên cứu, ngôn ngữ, độ sâu/độ dài và giới hạn nguồn/chi phí.
3. Nếu bật duyệt kế hoạch, đọc/sửa kế hoạch rồi mới cho workflow tiếp tục.
4. Trong workspace xem **Scientific Paper**, **Sources**, **Evidence & Citations**, **Experiments & Journal**, **Agent Runs & Cost** hoặc **Live Monitor**.
5. Bài tính toán: upload CSV được yêu cầu. Bài khảo sát/lab: thực hiện ở ngoài, khai báo nguồn gốc và upload dữ liệu để tiếp tục.
6. Mở nguồn kiểm tra claim, rà số liệu/kết luận và xuất bản thảo theo định dạng đang hỗ trợ.

### Các tab chính dùng để làm gì?

- **Scientific Paper:** đọc bản thảo và trạng thái.
- **Sources:** xem tài liệu đã thu thập.
- **Evidence & Citations:** lần từ claim/citation về đoạn nguồn được lưu.
- **Experiments & Journal:** cấu hình, kết quả, hình và nhật ký chạy.
- **Agent Runs & Cost / Live Monitor:** bước/role đã chạy, usage, lỗi và việc cần người dùng làm.
- **Metadata:** cấu hình và thuộc tính bài.
- **Hỏi đáp bài báo:** hỏi về bản thảo/bằng chứng đã lưu; câu trả lời không thay thế mở nguồn.

### Q&A Assistant có tìm nguồn mới không?

Luồng hỏi đáp dựa trên nội dung và trích đoạn bằng chứng đã lưu của phiên bản bài được chọn; đây không phải lượt nghiên cứu hoặc tìm kiếm web mới. Nó vẫn có thể cần model/quota. Khi thiếu bằng chứng, câu trả lời nên nêu rõ chưa đủ căn cứ.

### Bài chờ dữ liệu có chặn làm bài khác không?

Không cần giữ worker chạy trong lúc chờ. Bài và checkpoint được lưu; người dùng có thể mở bài khác. Số bài chạy đồng thời vẫn theo giới hạn hệ thống. Khi có dữ liệu, người dùng quay lại đúng task để tiếp tục.

### Nguồn lấy ở đâu? Số nguồn có đồng nghĩa chất lượng không?

Tùy cấu hình, hệ thống dùng OpenAlex, Crossref, Tavily và URL truy cập được, sau đó fetch/parse nội dung. Index record, abstract, landing page và full text là các mức nội dung khác nhau. Giới hạn `max_sources` là trần tài nguyên, không phải số nguồn chắc chắn thu được hoặc bằng chứng đã bao phủ lĩnh vực.

### Citation có chứng minh claim đúng không? Hệ thống chống bịa thế nào?

Citation/provenance giúp lần về nguồn và đoạn trích, nhưng không tự chứng minh claim đúng. Workflow tách kế hoạch khỏi kết quả đã thực hiện; nhánh thực nghiệm cần dữ liệu hoặc output runner; validator kiểm một số quy tắc cấu trúc/provenance. Các biện pháp giảm rủi ro nhưng không loại bỏ hoàn toàn lỗi model, nguồn hoặc diễn giải; con người cần kiểm tra.

### Hình trong bài được tạo thế nào? Có tìm ảnh trang trí không?

Ở luồng tính toán, biểu đồ dựa trên kết quả routine/dataset và phải được giải thích trong bài. Đây khác với tìm ảnh trang trí trên web. Tìm ảnh ngoài chưa phải cơ chế cốt lõi để chứng minh kết quả; nếu bổ sung cần xử lý license, attribution, lưu trữ và nguồn ảnh.

## 3. Agent và điều phối

### Có những agent nào? Curator và runner có phải agent không?

Năm vai trò AI thường dùng ở luồng REVIEW là **Supervisor, Researcher, Evidence Analyst, Writer, Critic**. Nhánh thực nghiệm có thêm **Methodologist**. Curator, router, experiment runner và validators là module/code, không phải tất cả đều agent AI.

### Các agent phối hợp thế nào?

Agent không phải các microservice tự do nhắn tin/giao việc cho nhau. Mỗi agent là một node trong LangGraph, nhận `ResearchState`, thực hiện nhiệm vụ và trả dữ liệu có cấu trúc. `StateGraph` cùng các hàm routing trong code quyết định node tiếp theo. Các bước quan trọng không để agent tự tạo đường đi tùy ý.

### Research loop và kiểm tra chéo chạy ra sao?

Writer tạo bản thảo rồi Critic trả verdict. Nếu cần sửa bản thảo, graph quay lại Writer; nếu thiếu bằng chứng và còn lượt, graph quay lại Researcher. Số vòng bị giới hạn. Cuối workflow có hậu xử lý/validator. Đây là kiểm tra nội bộ bằng model và code, không phải peer review độc lập hay chứng minh mọi claim đúng.

### Tại sao không chạy tất cả agent song song?

Các bước phụ thuộc kết quả trước: phân tích cần nguồn, viết cần evidence/kết quả, Critic cần draft. Vì vậy lõi dùng thứ tự và nhánh có điều kiện. Tác vụ độc lập có thể được song song hóa sau, nhưng phải giữ budget, state, idempotency và ghi nhận lỗi; chạy song song không tự làm kết quả chính xác hơn.

## 4. Kiến trúc và công nghệ

### Kiến trúc tổng thể là gì?

Đây là **modular monolith** ở cấp ứng dụng, triển khai thành frontend, API và worker; không tạo một microservice cho mỗi agent. Next.js gọi FastAPI; API xác thực và tạo job; Celery/Redis đưa job tới worker; worker chạy LangGraph; PostgreSQL/pgvector lưu task, nguồn, evidence, report và checkpoint; file artifacts lưu trong volume riêng.

### Vì sao chọn các công nghệ đó?

| Công nghệ | Vai trò | Trade-off |
|---|---|---|
| **Next.js / React** | Giao diện workspace và monitor | Cần quản lý state UI và tương thích API |
| **FastAPI / Pydantic** | API Python và kiểm tra dữ liệu | Cần quản lý async và version API |
| **LangGraph** | Node, nhánh, loop, interrupt và checkpoint cho workflow | Cần kiểm thử routing/state và recovery cẩn thận |
| **Celery + Redis** | Chạy việc dài ở nền qua hàng đợi | Phải xử lý redelivery, idempotency và trạng thái worker |
| **PostgreSQL + pgvector** | Lưu nghiệp vụ và vector retrieval trong một database | Cần quản lý migration, index và dung lượng |
| **Docker Compose** | Chạy các dịch vụ local có cấu hình lặp lại | Không tự cung cấp HA hay năng lực vận hành cloud |
| **Provider adapter** | Cho phép cấu hình model/provider qua kết nối được hỗ trợ | API tương thích không có nghĩa mọi model hỗ trợ giống nhau |

### LangGraph, Celery và Redis khác nhau thế nào?

**LangGraph** quyết định node/nhánh nào chạy tiếp bên trong workflow. **Celery** gửi và chạy job nền. **Redis** làm broker/backend hàng đợi. Redis không quyết định agent nào nên chạy; logic đó ở graph và code.

### `ResearchState` là gì?

State có cấu trúc dùng chung giữa node: ID task/run, câu hỏi, kế hoạch, nguồn, claim/evidence, dữ liệu, draft, verdict, budget và trạng thái. Node cập nhật state để bước kế tiếp tiếp tục. API key không được đưa vào graph state.

### Dev và prod đã chia chưa?

Đã tách hai môi trường **local** bằng cùng `docker-compose.yml` nhưng Compose profiles/projects, cổng, secrets, database/Redis/artifact volumes riêng. Dev chạy bằng `scripts/dev.ps1` (mặc định UI 3000, API 8000); release/demo trên máy này chạy bằng `scripts/release.ps1` ở cổng 3082. Code dev không tự cập nhật release; cần kiểm tra, commit và deploy theo quy trình.

**Cần nói rõ:** “prod” ở đây là profile/release image chốt để demo local, không có nghĩa đã triển khai public hoặc đạt đủ yêu cầu vận hành production doanh nghiệp.

### Hệ thống có dùng MCP không? MCP hữu ích gì?

**Hiện chưa dùng MCP trong luồng runtime cốt lõi.** Search/model gọi qua adapter và tool hiện có. MCP (Model Context Protocol) có thể chuẩn hóa kết nối agent với tool/resource server, ví dụ kho tài liệu, Zotero hoặc một nguồn học thuật.

MCP là hướng mở rộng, không phải điều kiện để gọi hệ thống là multi-agent. Nếu tích hợp cần allowlist tool/server, quyền, credential, timeout, budget và audit; không cho server tùy ý truy cập filesystem, mạng nội bộ hoặc chạy code. Chỉ nên thêm khi có nhu cầu rõ và bài đánh giá tương ứng.

### Công nghệ nào có thể cải thiện trong tương lai?

| Nhu cầu | Hướng xem xét | Điều kiện |
|---|---|---|
| Theo dõi request xuyên API/worker/provider | OpenTelemetry; metrics/traces, Prometheus/Grafana | Không ghi key, prompt nhạy cảm hoặc dữ liệu riêng vào telemetry |
| Thêm connector nguồn | MCP có kiểm soát hoặc adapter chuyên biệt | Kiểm quota, license, metadata, coverage và dedup |
| Chạy code nghiên cứu linh hoạt | gVisor/Firecracker hoặc sandbox chuyên dụng | Threat model, giới hạn mạng/CPU/RAM/time, kiểm file và security review; runner hiện tại không phải sandbox arbitrary code |
| Lưu file/artifacts trên nhiều máy | S3-compatible storage | Phân quyền, mã hóa, lifecycle và backup/restore |
| Đo chất lượng nghiên cứu | Benchmark, expert rubric, blind review, single-agent baseline | Cùng model/nguồn/budget, thẩm định độc lập và báo cáo uncertainty |
| Mở cho nhiều tổ chức | RBAC/tenant isolation, audit log, secret manager | Kiểm thử bảo mật, privacy, vận hành và incident response |

Đây là đề xuất tương lai, chưa phải thành phần đã triển khai đầy đủ trong bản demo.

## 5. Provider, bảo mật và chi phí

### Người dùng nhập API key được không? Có miễn phí không?

Có giao diện Settings để lưu kết nối model và chọn cấu hình cho bài. Key được mã hóa khi lưu; server giới hạn API base URL vào các địa chỉ tin cậy, không mở thành proxy gọi URL tùy ý. Model miễn phí vẫn có quota, rate limit và giới hạn context/output. Nếu dùng dịch vụ trả phí, phí theo provider; USD trong ứng dụng là ước tính theo giá khai báo, không phải hóa đơn.

### Vì sao dùng API tương thích OpenAI?

Một adapter chung giảm số nhánh tích hợp cho các provider có giao diện chat tương thích. Tuy nhiên model/provider khác nhau về model ID, JSON schema, tool calling, reasoning và quota. Kiểm tra key/model thành công không đảm bảo bài dài sẽ chạy hết.

### Dữ liệu và API key được bảo vệ thế nào?

Key không gửi lại trình duyệt sau khi lưu; code dùng Fernet encryption và gắn kết nối với user/task theo ngữ cảnh. Backend kiểm quyền sở hữu task. Bản local giữ secrets và volume riêng. Khi gửi câu hỏi/nguồn tới provider ngoài, dữ liệu vẫn được xử lý bởi provider đó; không nên nhập thông tin nhạy cảm nếu chưa xem chính sách và có thẩm quyền phù hợp.

### Có chạy code do AI sinh không? Runner đã an toàn chưa?

Bản hiện tại chỉ chạy routine được hỗ trợ trên CSV; không cho LLM sinh arbitrary code rồi thực thi. Có giới hạn dữ liệu/process nhưng không nên quảng bá là sandbox chống mã độc production-grade. Chạy code tùy ý cần cách ly mạnh như microVM/dịch vụ chuyên dụng cùng threat model và kiểm thử bảo mật.

## 6. Kiểm thử, đánh giá và giới hạn

### Đã kiểm thử những gì?

Repo có backend tests, frontend tests, syntax/build/container checks và GitHub Actions CI; các script riêng kiểm tra môi trường local/release. Khi bảo vệ, chỉ nêu kết quả test mới nhất kèm đúng commit. Test pass chứng minh case đã viết được kiểm tra, không chứng minh mọi model/provider hoặc chất lượng khoa học của mọi bài.

### Đánh giá chất lượng multi-agent thế nào?

Tách ba lớp: (1) kỹ thuật—routing, owner isolation, retry/resume; (2) nội dung—evidence/citation, cấu trúc, số liệu; (3) hiệu quả multi-agent—so với single-agent baseline trên cùng câu hỏi, model, nguồn, budget và rubric. Hiện chưa có benchmark đủ để kết luận multi-agent tốt hơn; đây là phần cần pilot evaluation tiếp.

### Vì sao bài có thể dừng hoặc cần review?

Provider có thể quá tải/hết quota; model có thể trả JSON lỗi, bị cắt hoặc timeout; nguồn/dữ liệu có thể thiếu; budget có thể hết; validator/Critic có thể yêu cầu sửa. Retry có giới hạn để tránh lặp vô tận. Cần đọc bước/lỗi trong Monitor; đổi model không sửa được mọi nguyên nhân.

### Có giữ kết quả âm không?

Định hướng là lưu kết quả phép thử, kể cả khi model không cải thiện baseline; không chọn lọc chỉ giữ kết quả đẹp. Nhật ký, dữ liệu và cấu hình giúp truy nguyên. Khi trả lời cần phân biệt chính sách được thiết kế với các case đã thật sự kiểm thử.

### Các hạn chế quan trọng?

- Ba luồng hiện tại không bao phủ mọi loại nghiên cứu/chuẩn xuất bản.
- Nguồn có thể thiếu full text, bị paywall hoặc không bao phủ hết literature.
- Model, Critic và validator có thể sai; người dùng phải review.
- Runner hỗ trợ routine xác định trước, chưa phải môi trường notebook/arbitrary code.
- Chưa chứng minh multi-agent tốt hơn baseline qua benchmark độc lập.
- Quota provider, mạng và latency ảnh hưởng việc chạy.
- Release demo là Docker local, chưa phải dịch vụ public/enterprise production.

### Có thể gọi là production-ready không?

Không nên gọi bản demo local là production-ready cho doanh nghiệp. Có quy trình release, migration, health checks, backup/restore và giới hạn container; vẫn cần security/privacy review, RBAC/tenant, monitoring/alerting, load test, backup recovery drill, incident response, SLA và xác nhận đạo đức/pháp lý trước triển khai thật.

## 7. Câu hỏi khó và lời đáp ngắn

| Thầy có thể hỏi | Gợi ý trả lời |
|---|---|
| “AI ngoài kia đã viết được bài báo, sao cần dự án này?” | “Synthia không hứa viết hay hơn. Em tập trung tổ chức quy trình và lưu nguồn/bằng chứng/kết quả để có thể kiểm tra. Muốn nói tốt hơn sản phẩm khác cần benchmark trực tiếp.” |
| “Multi-agent chắc tốt hơn một agent chứ?” | “Không chắc. Chia vai có thể làm rõ nhiệm vụ nhưng tăng số request, chi phí và lỗi. Em cần so với single-agent baseline.” |
| “Critic đồng ý thì bài đúng chưa?” | “Chưa. Đó là kiểm tra nội bộ; người dùng vẫn kiểm nguồn, phép tính, phương pháp và kết luận.” |
| “Research gap có phải phát hiện mới chắc chắn?” | “Không. Đó là gap ứng viên trong phạm vi nguồn/truy vấn đã thu thập, cần kiểm tra thêm.” |
| “Tại sao chưa dùng MCP?” | “Connector hiện đủ cho luồng mục tiêu. MCP không tự cải thiện chất lượng; em sẽ tích hợp khi có tool cụ thể, kiểm soát an toàn và tiêu chí đánh giá.” |
| “Dev/prod đã chia chưa?” | “Có tách profile, project, cổng, secrets và data volumes local. Release vẫn chạy trên máy demo, không phải cloud production.” |
| “Kết quả tái lập có nghĩa là đúng không?” | “Không. Chạy lại khớp điều kiện đã lưu chỉ hỗ trợ tái lập phép thử, không chứng minh thiết kế khoa học đúng hoặc kết quả khái quát.” |
| “Đây có novelty khoa học không?” | “Hiện là đồ án hệ thống/workflow. Novelty khoa học cần câu hỏi riêng, benchmark, baseline và đánh giá thực nghiệm; em không khẳng định khi chưa có bằng chứng.” |

## 8. Những điều không nên khẳng định

- “Bài tự động đạt Q1, chắc chắn được chấp nhận hoặc sẵn sàng xuất bản.”
- “Critic loại hết hallucination”; “citation tồn tại nên claim đúng.”
- “Đã tìm hết literature/đã systematic review” nếu chưa chạy protocol tương ứng.
- “Multi-agent tốt hơn single-agent” khi chưa có đối chứng.
- “Mọi model đều chạy được”; “API miễn phí không giới hạn”; “đổi key là reset quota.”
- “Runner an toàn để chạy code bất kỳ.”
- “Đã triển khai enterprise/cloud production” khi đang demo Docker local.
- Dùng kết quả offline/mock/synthetic như kết quả live hoặc dữ liệu người thật.

## 9. Đọc thêm khi cần trả lời sâu

- [Agent workflow](agent-workflow.md) — vai trò, state, routing và research loop.
- [System design](../architecture/system-design.md) và [technical design](../architecture/technical-design.md) — kiến trúc/module.
- [Local release](local-release.md) — dev/demo, secrets, lệnh chạy và dữ liệu tách biệt.
- [Experiment journal and reproducibility](experiment-journal-and-reproducibility.md) — routine và tái lập.
- Code graph: `backend/app/agents/graph.py`, `state.py`, `nodes.py`.
- Worker/dispatch: `backend/app/worker.py`, `backend/app/services/task_dispatcher.py`.
- Search: `backend/app/tools/scholarly_search.py`, `search.py`, `scraper.py`.
- Q&A/model/runner: `backend/app/services/report_question_answering.py`, `model_connection.py`, `experiment_runner.py`.
- CI: `.github/workflows/ci.yml`.
