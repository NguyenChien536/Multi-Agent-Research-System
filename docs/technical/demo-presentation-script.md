# Kịch bản thuyết trình và demo Synthia

**Người trình bày:** Nguyễn Đình Chiến. **Thời lượng:** khoảng 12–15 phút nói và thao tác; không tính thời gian chờ model. Đây là lời dẫn để diễn tập, không cần đưa toàn bộ chữ lên slide.

**Thông điệp chính:** từ câu hỏi đến bản thảo có bằng chứng, với ba cách lấy bằng chứng: đọc tài liệu, chạy tính toán và chờ con người thu thập dữ liệu.

## 1. Chuẩn bị trước khi nói

Khởi động bằng `.\scripts\release.ps1 -Action start` tại thư mục gốc, mở http://127.0.0.1:3082. Đăng nhập và cấu hình API/model ở Settings trước khi chia sẻ màn hình.

Mở sẵn ba bài đã diễn tập và một task khảo sát riêng còn chờ. Nếu chưa có kết quả thành công, để nguyên trạng thái, không lấy bảng offline đóng vai kết quả vừa sinh. [Hướng dẫn demo](demo-guide.md) có bước thao tác và cách xử lý lỗi.

| Bài | Tên gợi ý | Loại chọn | Input |
|---|---|---|---|
| A | Spaced Practice and Delayed Retention: A Critical Narrative Review | REVIEW | Không bắt buộc file |
| B | Synthetic Electricity Demand: Ridge Regression versus a Mean Baseline | EMPIRICAL_COMPUTATIONAL | computational-electricity-synthetic.csv |
| C | AI Research Assistants: A Synthetic Descriptive Survey Demonstration | EMPIRICAL_HUMAN | human-survey-synthetic.csv và human-form-inputs.json |

File ở `examples/demo/`. Dùng STANDARD, MEDIUM, English, tối đa 12 nguồn và 2 vòng; APA cho A/C, IEEE cho B. Bật duyệt kế hoạch ở A. Chạy diễn tập lần lượt; model miễn phí không có thời gian hoàn tất cố định.

## 2. Mở đầu: vấn đề và mục tiêu — 1 phút

**Hiển thị:** tên dự án và dashboard.

**Lời nói:**

> Em xin trình bày Synthia — Multi-Agent Research System, hệ thống hỗ trợ người nghiên cứu từ câu hỏi đến bản thảo bài báo có nguồn và bằng chứng.
>
> Synthia là ứng dụng web: người dùng thao tác bằng trình duyệt, còn phiên bản demo này chạy cục bộ bằng Docker trên máy của em. Về kiến trúc, hệ thống có thể phát triển thành ứng dụng nội bộ cho nhóm nghiên cứu hoặc doanh nghiệp. Tuy nhiên, bản demo hiện tại chưa được nghiệm thu là dịch vụ production cho doanh nghiệp.
>
> Khi làm nghiên cứu, khó khăn không chỉ là viết đủ Abstract, Introduction hay Conclusion. Người nghiên cứu còn phải tìm tài liệu, kiểm bằng chứng, chọn phương pháp, thu thập hoặc chạy dữ liệu rồi xem kết luận có được hỗ trợ hay không. Nếu chỉ yêu cầu AI viết ngay, những bước này khó theo dõi và có thể bị trộn lẫn giữa điều dự kiến làm với kết quả đã thực sự thu được.
>
> Mục tiêu của em là tổ chức công việc đó thành một quy trình có phân vai, lưu trạng thái và cho phép đối chiếu nguồn gốc kết quả. Đầu ra là bản thảo hỗ trợ nghiên cứu; người dùng vẫn kiểm chứng và chịu trách nhiệm khi sử dụng.

**Lưu ý cần nói rõ:**

> AI có thể bịa tài liệu tham khảo, trích dẫn sai hoặc diễn giải nhầm số liệu. Vì vậy, người nghiên cứu phải kiểm tra từng nguồn, đoạn bằng chứng, con số, phương pháp và kết luận trước khi dùng hoặc gửi bài. Bản thảo do Synthia tạo không đồng nghĩa với bài đã được bình duyệt hay sẵn sàng xuất bản.

## 3. Vì sao có ba luồng nghiên cứu? — 1–2 phút

**Hiển thị:** ba lựa chọn trên form tạo bài; chỉ vào từng lựa chọn khi nói.

> Không phải câu hỏi nào cũng trả lời được chỉ bằng cách đọc tài liệu. Vì thế em chia thành ba luồng theo cách lấy bằng chứng.
>
> **Luồng thứ nhất là tổng quan tài liệu:** đọc các công trình đã công bố để biết đã hiểu gì, còn bất đồng hay thiếu gì. Ví dụ, luyện tập giãn cách giúp ghi nhớ lâu hơn trong điều kiện nào? Bằng chứng đến từ nghiên cứu trước, hệ thống không tự tạo ra thí nghiệm mới.
>
> **Luồng thứ hai là thực nghiệm tính toán:** phải chạy phép thử trên dữ liệu. Ví dụ, trên file điện năng được cung cấp, Ridge có giảm sai số so với cách luôn dự đoán bằng trung bình không? Bằng chứng là số liệu chương trình thực sự tính, không phải model tự viết.
>
> **Luồng thứ ba là nghiên cứu ngoài hệ thống:** dữ liệu cần con người thu thập, như khảo sát sinh viên, đo trong lab hoặc quan sát thực địa. Hệ thống soạn đề cương rồi dừng chờ. Người dùng tải dữ liệu lên thì bài mới tiếp tục. Chưa có dữ liệu thì không được viết Results như nghiên cứu đã xong.
>
> Ba luồng không phải ba ngành riêng và cũng không bao quát mọi phương pháp khoa học. Chúng giúp hệ thống chọn đúng cách làm, tránh đánh đồng tài liệu, số liệu thực chạy và dữ liệu do người dùng cung cấp.

**Câu nhớ ngắn:** “Đọc tài liệu — chạy phép thử — chờ người thu thập dữ liệu.”

## 4. Synthia khác gì chatbot và một AI agent? — 2–3 phút

**Hiển thị:** sơ đồ kiến trúc, bảng so sánh và Agent Monitor.

### 4.1. Điểm khác biệt cốt lõi: Chatbot vs Đơn Agent vs Hệ thống Đa tác nhân

> **Điểm khác biệt cốt lõi nằm ở cơ chế tự chủ (autonomy), sự chuyên môn hóa và vòng lặp kiểm chứng thay vì chỉ phản hồi thụ động dựa trên một câu lệnh (prompt) duy nhất.**

Dưới đây là bảng so sánh chi tiết giúp dễ hình dung:

| Tiêu chí | Chatbot (VD: ChatGPT thông thường) | Đơn Agent (1 AI Agent đơn lẻ) | Hệ thống Đa tác nhân (Synthia Multi-Agent) |
|---|---|---|---|
| **Cách vận hành** | **Hỏi - Đáp thụ động:** Bạn hỏi gì đáp nấy trong một luồng hội thoại duy nhất. | **Tự chủ theo mục tiêu:** Bạn giao 1 mục tiêu, AI tự lên kế hoạch và thực hiện các bước để hoàn thành. | **Phối hợp theo quy trình:** Nhiều AI đóng vai các chuyên gia khác nhau, tự giao việc và kiểm tra chéo cho nhau qua trạng thái chung. |
| **Khả năng dùng công cụ** | **Hạn chế:** Chủ yếu dựa vào dữ liệu đã học trước đó hoặc tìm kiếm web cơ bản. | **Có thể tự gọi công cụ:** Tự tìm kiếm, chạy code tính toán hoặc đọc file PDF trong một luồng đơn. | **Công cụ chuyên biệt theo vai:** Mỗi Agent sở hữu bộ công cụ riêng (Agent tìm kiếm học thuật, Agent trích xuất vector embeddings, Agent chạy routine thống kê, Agent chuẩn hóa định dạng trích dẫn). |
| **Chất lượng & Độ sâu** | **Dễ viết lan man, hời hợt:** Dễ đuối sức hoặc mất mạch logic khi yêu cầu tạo bài nghiên cứu dài hàng chục trang. | **Dễ quá tải ngữ cảnh (Context Overload):** Vừa phải đọc tài liệu, vừa trích xuất bằng chứng, vừa tính toán và viết bài trong cùng một context window. | **Chuyên sâu và chặt chẽ:** Từng phần việc được phân công độc lập cho từng Agent chuyên trách với bộ chỉ dẫn (System Prompt) và schema dữ liệu riêng. |
| **Kiểm soát ảo giác (Hallucination)** | **Rất cao:** Rất hay tự bịa tên tác giả, năm xuất bản, DOI hoặc số liệu nghiên cứu do cơ chế sinh từ tiếp theo. | **Trung bình:** Có thể tự kiểm tra lại nếu được lập trình bước rà soát, nhưng dễ bỏ sót lỗi do "vừa đá bóng vừa thổi còi". | **Thấp nhất:** Có **Critic Agent (Reviewer)** đóng vai trò "người phản biện khó tính", độc lập soi lỗi trích dẫn, bắt lỗi số liệu và yêu cầu Writer Agent viết lại nếu chưa đạt. |

#### Ví dụ thực tế để thấy rõ sự khác biệt

Giả sử bạn yêu cầu: *"Viết tổng quan tài liệu (Literature Review) về tác động của AI trong chẩn đoán ung thư phổi giai đoạn 2020–2025."*

- **Với Chatbot (ChatGPT thông thường):** Nó sẽ sinh ra ngay lập tức một bài viết dài khoảng 1.000 chữ dựa trên trí nhớ đã học. Văn phong rất mượt, nhưng 50% tài liệu trích dẫn bên trong có thể là do nó tự bịa ra (ảo giác tác giả, bài báo không tồn tại), và nội dung mang tính chất nhận định chung chung.
- **Với 1 AI Agent đơn lẻ:** Nó sẽ tự động lên mạng tìm kiếm các bài báo thật trên Google Scholar, tải về, đọc tóm tắt rồi tự viết thành bài báo. Tuy nhiên, vì một mình phải gánh quá nhiều tác vụ cùng lúc (tìm kiếm, lọc, đọc hiểu, phân tích mâu thuẫn, soạn thảo), ngữ cảnh dễ bị loãng, bài viết dễ bị lủng củng hoặc thiếu tính phản biện sâu sắc.
- **Với Hệ thống Multi-Agent (Synthia):**
  1. **Supervisor Agent** phân tích đề tài, lập đề cương nghiên cứu và sinh ra 5–7 truy vấn tìm kiếm chuyên sâu theo các chủ đề con.
  2. **Researcher & Curator Agent** tìm đúng các bài báo uy tín từ PubMed / arXiv / Semantic Scholar, tải về, băm nhỏ (chunking) và lưu vào cơ sở dữ liệu vector.
  3. **Evidence Analyst Agent** đọc dữ liệu đã băm, trích xuất ma trận bằng chứng (Evidence Matrix) và phát hiện các điểm mâu thuẫn hoặc khoảng trống nghiên cứu giữa các tác giả.
  4. **Writer Agent** dựa trực tiếp trên ma trận bằng chứng đã xác thực để soạn thảo từng phần học thuật (Introduction, Methods, Results, Discussion).
  5. **Critic Agent (Reviewer)** đọc lại toàn bộ bản thảo, đối chiếu từng câu với đoạn văn gốc. Nếu phát hiện câu khẳng định thiếu căn cứ hoặc trích dẫn sai số liệu, nó từ chối phê duyệt và trả bài yêu cầu Writer sửa lại cho đến khi chuẩn xác mới bàn giao cho người dùng.

---

### 4.2. Cách chia vai trò các Agent trong Synthia

Synthia chia nhỏ quy trình nghiên cứu khoa học khắt khe thành **7 Agent chuyên môn hóa**:

1. **Supervisor Agent (Chỉ đạo & Lập kế hoạch):**
   - Phân tích câu hỏi nghiên cứu, xác định loại hình (Tổng quan lý thuyết / Thực nghiệm tính toán / Khảo sát thực địa).
   - Thiết lập đề cương, phạm vi nghiên cứu và tạo các truy vấn tìm kiếm chiến lược.
   - Hỗ trợ cơ chế **Human-in-the-Loop** để người dùng xem và phê duyệt kế hoạch trước khi chạy.
2. **Researcher Agent (Tìm kiếm học thuật):**
   - Thực thi các câu truy vấn học thuật qua API bên ngoài (PubMed, arXiv, CrossRef, Semantic Scholar).
   - Đảm bảo các bài báo thu thập được là tài liệu thực tế có thể đối chiếu nguồn gốc (provenance).
3. **Curator Agent (Xử lý & Lập chỉ mục tri thức):**
   - Đọc tệp PDF do người dùng tải lên hoặc bài báo tải về, bóc tách cấu trúc văn bản.
   - Phân đoạn văn bản (chunking) và tạo vector embeddings để lưu vào vector database (pgvector).
4. **Evidence Analyst Agent (Phân tích ma trận bằng chứng):**
   - Rút trích các phát hiện cốt lõi (findings), phương pháp và số liệu định lượng từ các nguồn tài liệu.
   - Tổng hợp thành ma trận bằng chứng, đối chiếu các quan điểm đồng thuận hoặc mâu thuẫn.
5. **Writer Agent (Soạn thảo học thuật):**
   - Viết từng phân đoạn của bài báo khoa học theo cấu trúc chuẩn IMRaD (Introduction, Methods, Results, Discussion).
   - Chỉ được viết dựa trên ma trận bằng chứng và tài liệu tham khảo thực có trong cơ sở dữ liệu, không tự do bịa đặt.
6. **Critic Agent (Phản biện & Kiểm định độc lập):**
   - Đóng vai reviewer bình duyệt: rà soát tính logic, kiểm tra chéo trích dẫn với các đoạn bằng chứng gốc.
   - Bắt lỗi các khẳng định chưa được chứng minh (unsupported claims) hoặc lỗi số liệu; đưa ra nhận xét chi tiết và trả bài yêu cầu viết lại.
7. **PostProcessor Agent (Chuẩn hóa trích dẫn & Xuất bản):**
   - Chuẩn hóa định dạng tài liệu tham khảo theo đúng phong cách yêu cầu (IEEE, APA, Harvard).
   - Kiểm tra tính toàn vẹn của danh mục tài liệu tham khảo và định dạng đầu ra (Markdown, Word .docx, PDF).

---

### 4.3. Cơ chế điều phối (Orchestration & Workflow)

Các Agent trong Synthia không trò chuyện hỗn loạn hay tự do gọi nhau, mà được điều phối theo một kiến trúc chặt chẽ:

- **LangGraph StateGraph (Đồ thị trạng thái có hướng):**
  - Toàn bộ tiến trình nghiên cứu là một đồ thị máy trạng thái hữu hạn (State Machine).
  - Dữ liệu giữa các agent được truyền nhận an toàn thông qua một `ResearchState` dùng chung, lưu trữ trạng thái bất biến qua từng bước.
- **Vòng lặp phản biện có điều kiện (Conditional Review & Backtracking Loop):**
  - Sau bước của Writer, đồ thị chuyển sang Critic. Critic đánh giá chất lượng; nếu đạt điểm ngưỡng, luồng mới đi tiếp sang PostProcessor.
  - Nếu Critic phát hiện lỗi, hệ thống tự động rẽ nhánh quay ngược lại (backtrack) để Writer chỉnh sửa hoặc Researcher tìm kiếm thêm nguồn. Vòng lặp được khống chế số lần tối đa (max iterations) để đảm bảo không bị loop vô hạn.
- **Tương tác có con người (Human-in-the-Loop):**
  - Cho phép người dùng duyệt đề cương nghiên cứu (Plan Approval) trước khi tốn tài nguyên tìm kiếm.
  - Ở luồng thực nghiệm ngoài hệ thống (Empirical Human), đồ thị tạm dừng ở trạng thái `WAITING_USER_DATA`, chờ người dùng nạp dữ liệu khảo sát thực tế rồi mới tiếp tục phân tích.
- **Hạn mức an toàn bền vững (Fail-closed Budget Guard & Checkpoint):**
  - Giám sát nghiêm ngặt số lượt gọi LLM, token và chi phí trước mỗi thao tác.
  - Khi chạm trần, bài tự động tạm dừng (PAUSE), bảo toàn nguyên vẹn bài viết đã tạo và checkpoint trong cơ sở dữ liệu, cho phép người dùng xem minh bạch thông số và bấm duyệt tiếp tục mà không bị mất bài.

---

### 4.4. Ngăn xếp công nghệ của hệ thống (Technology Stack)

Synthia được xây dựng trên nền tảng công nghệ hiện đại, đảm bảo tính bền vững và khả năng mở rộng:

- **AI & Đa tác tử (Multi-Agent Engine):**
  - `LangGraph`: Xây dựng StateGraph, quản lý luồng điều phối tác tử, checkpoint và backtracking.
  - `LangChain`: Tích hợp các model LLM (OpenAI, Anthropic, Gemini, OpenRouter) và các công cụ tìm kiếm học thuật.
  - `Pydantic`: Định nghĩa cấu trúc dữ liệu nghiêm ngặt (Strict Schema Validation) cho mọi kết quả trung gian giữa các Agent, loại bỏ lỗi lệch định dạng JSON.
- **Backend & Hàng đợi tác vụ (Backend & Task Queue):**
  - `Python 3.11` & `FastAPI`: Xây dựng REST API hiệu năng cao, bất đồng bộ hoàn toàn (`async/await`).
  - `Celery` kết hợp `Redis`: Quản lý hàng đợi và thực thi các bài nghiên cứu dài hạn trong worker ngầm, tách biệt hoàn toàn khỏi luồng HTTP web server để đảm bảo không bao giờ bị timeout request.
- **Cơ sở dữ liệu & Lưu trữ tri thức (Database & Knowledge Store):**
  - `PostgreSQL 16`: Lưu trữ thông tin người dùng, nhiệm vụ nghiên cứu, các phiên bản bài viết và nhật ký kiểm toán (audit log).
  - `pgvector`: Extension PostgreSQL chuyên dụng để lưu trữ và truy vấn tương đồng vector embeddings (RAG) phục vụ đối chiếu trích dẫn.
  - `Alembic`: Quản lý migration schema cơ sở dữ liệu an toàn.
- **Frontend & Giao diện người dùng:**
  - `Next.js 15` (App Router) & `React 19`: Xây dựng giao diện web tương tác mượt mà, hỗ trợ render tối ưu.
  - `TypeScript` & `Tailwind CSS`: Đảm bảo type-safety và thiết kế giao diện màu sáng hiện đại, tương phản cao, tối ưu cho việc đọc tài liệu học thuật.
  - `EventSource / Polling Monitor`: Cập nhật tiến độ của từng Agent theo thời gian thực (Real-time Agent Monitor & Pipeline Steps).

---

### 4.5. Lời nói dẫn dắt của người trình bày (1–2 phút)

> *"Điểm khác biệt cốt lõi của Synthia so với một chatbot hay một AI agent đơn lẻ nằm ở 3 yếu tố: **cơ chế tự chủ theo mục tiêu**, **sự chuyên môn hóa thành 7 tác tử độc lập**, và **vòng lặp kiểm chứng chéo chặt chẽ**.*
>
> *Thay vì để một AI duy nhất vừa đọc tài liệu, vừa phân tích, vừa viết và dễ bị 'ảo giác' hay quá tải ngữ cảnh, Synthia dùng LangGraph tổ chức thành một quy trình khoa học: Supervisor lập kế hoạch, Researcher và Curator gom và đánh chỉ mục tài liệu vào pgvector, Evidence Analyst trích xuất ma trận bằng chứng, Writer chấp bút theo cấu trúc chuẩn IMRaD, và đặc biệt là Critic Agent độc lập đóng vai người phản biện khó tính để bắt lỗi trích dẫn và yêu cầu sửa lại.*
>
> *Toàn bộ quy trình chạy ngầm qua Celery và Redis, có lưu vết checkpoint và quản lý trần chi phí an toàn, giúp người nghiên cứu kiểm tra được tường tận nguồn gốc của từng câu khẳng định trong bài báo."*

## 5. Demo A — Tổng quan tài liệu — 2 phút

**Giải thích câu hỏi:** “Trong những điều kiện nào luyện tập giãn cách giúp người trưởng thành hoặc sinh viên ghi nhớ lâu hơn luyện tập dồn?”

**Nội dung copy vào ô câu hỏi:**

~~~text
Under what conditions does spaced practice improve delayed retention compared with massed practice in adult or university learners? Prepare a critical narrative review. Compare practice schedules, retention intervals, outcome measures and populations, including conflicting findings and limits on transfer. Use relevant primary research and credible scholarly syntheses, and cite the evidence actually retrieved. Report the real search queries, index providers, eligibility criteria and search limitations; do not claim an exhaustive systematic review. Write academic English prose with meaningful subsections in substantial sections and explain any figures or tables. Distinguish supported conclusions from tentative research gaps.
~~~

| Thao tác | Nói gì? | Cho thầy xem gì? |
|---|---|---|
| Chọn REVIEW, bật duyệt kế hoạch, bắt đầu | “Trước khi viết, hệ thống lập phạm vi và cách tìm tài liệu; em có thể duyệt hoặc yêu cầu sửa.” | Kế hoạch thật của bài |
| Mở Agent Monitor | “Em xem được bước đang chạy và lịch sử xử lý, không chỉ một biểu tượng loading.” | Agent/bước và kết quả thực tế |
| Chuyển sang bài A đã chạy trước, nếu có | “Đây là kết quả đã diễn tập trước trên cùng hệ thống để không phụ thuộc thời gian chờ model.” | Bản thảo đã lưu |
| Mở Bài báo, Nguồn, Bằng chứng & Trích dẫn | “Em kiểm khẳng định này dựa trên công trình và đoạn bằng chứng nào.” | Một claim cụ thể và đoạn nguồn hỗ trợ |
| Mở Discussion/Limitations | “Bài cần so sánh điều kiện và hạn chế, không chỉ liệt kê các nghiên cứu.” | Mục con, tổng hợp và giới hạn |

**Nếu muốn thử hỏi về bài:**

~~~text
Which evidence supports the claim that retention interval affects the spacing benefit, and what limitations remain?
~~~

**Không nói:** đã tổng quan hết tài liệu, đã hoàn thành systematic review/PRISMA hoặc citation tồn tại đồng nghĩa kết luận chắc chắn đúng.

## 6. Demo B — Thực nghiệm tính toán — 3 phút

**Giải thích câu hỏi:** “Trên dữ liệu điện năng mô phỏng này, Ridge có giảm sai số so với dự đoán bằng trung bình không?”

**Nội dung copy:**

~~~text
On the supplied SYNTHETIC electricity-demand CSV, how does the supported tabular_regression_v1 Ridge regression routine compare with a training-mean baseline on its recorded held-out split? Use temperature and occupied_hours to predict target. Run the supported routine and report its actual MAE, RMSE and R-squared, train-only preprocessing, split, seed and repeatability. Present a baseline comparison table and explain the generated figures. Write a computational paper-style draft with meaningful Methods, Experimental Setup, Results and Discussion subsections. Literature is for background, not a substitute for measured results. This is a synthetic demonstration, not a novel algorithm, causal study or real-world forecasting validation. Do not claim cross-validation, significance tests or multiple seeds were run.
~~~

**Tệp upload:** [computational-electricity-synthetic.csv](../../examples/demo/computational-electricity-synthetic.csv), gồm 120 dòng. Đầu vào là `temperature`, `occupied_hours`; đích cần dự đoán là `target`.

| Thao tác | Lời nói | Cho thầy xem gì? |
|---|---|---|
| Chọn tính toán và tạo bài | “Câu hỏi này cần số đo thực chạy; chỉ đọc tài liệu là chưa đủ.” | Đúng loại nghiên cứu |
| Khi chờ dữ liệu, mở Experiments và upload CSV | “Đây là dữ liệu mô phỏng, không phải số điện đo tại tòa nhà thật. Phiên bản này chạy một routine hồi quy cố định.” | Dataset được nhận, đủ 120 dòng |
| Mở bài B đã chạy xong nếu có | “Baseline là cách đơn giản: luôn dự đoán trung bình của dữ liệu train. Mô hình được so trên cùng split.” | Bảng baseline và Ridge |
| Mở biểu đồ và Results | “Số liệu trong bài phải khớp runner, hình phải có giải thích.” | Một hình và phần diễn giải |
| Mở journal và gói chạy lại nếu có | “Ở đây lưu cấu hình và kết quả để kiểm lại phép thử.” | Seed, split, routine và thông tin tái lập |

**Đối chiếu từ kiểm offline trên đúng CSV, không phải kết quả vừa tạo qua web:**

| Chỉ số | Baseline | Ridge |
|---|---:|---:|
| MAE | 12.338741 | 1.335145 |
| RMSE | 14.210697 | 1.468646 |
| R² | -0.012568 | 0.989185 |

**Lời giải thích:**

> MAE và RMSE là sai số, nhỏ hơn tốt hơn. Routine dùng seed 42, 96 dòng train và 24 dòng test, Ridge alpha=1; chuẩn hóa chỉ học từ train. Nếu kết quả thực chạy khớp, em chỉ kết luận về phép thử và bộ dữ liệu này. Chưa có căn cứ nói mô hình tốt nhất, tốt cho mọi dữ liệu hoặc có ý nghĩa thống kê.

**Nếu còn thời gian:** dùng task khác để chạy [negative control](../../examples/demo/computational-negative-control-synthetic.csv). Hai features hằng số, kết quả offline là `NO_IMPROVEMENT`, delta MAE=0. Nói: “Nếu không cải thiện thì hệ thống vẫn giữ kết quả, không làm đẹp số liệu để có bài hay hơn.”

## 7. Demo C — Khảo sát, chờ và tiếp tục — 3 phút

**Giải thích câu hỏi:** “Khảo sát mô tả cho biết sinh viên cảm nhận trợ lý AI hữu ích đến đâu và cần bỏ công sức kiểm chứng như thế nào?”

**Nội dung copy:**

~~~text
How can an exploratory descriptive survey characterize perceived usefulness and verification effort when university students use AI research assistants? Prepare a protocol, then wait for a result file and provenance. For this SOFTWARE DEMONSTRATION I will upload 24 SYNTHETIC responses, not data collected from real people. After upload, write an empirical-style draft with meaningful subsections, explicitly labeling the data as synthetic in the Abstract, Methods, Results and Conclusion. Report only uploaded or computed descriptive statistics, specifying sample versus population SD. Do not invent recruitment, ethics approval, instrument validation, p-values, causal effects or generalizability. Explain how genuine future data collection would differ.
~~~

**Lời dẫn:** “Nếu làm thật, người dùng phải thu thập dữ liệu theo quy trình phù hợp. Hôm nay em dùng 24 dòng mô phỏng để minh họa phần mềm, không tuyên bố đã khảo sát 24 người.”

| Thao tác | Lời nói | Cho thầy xem gì? |
|---|---|---|
| Mở bài C đang chờ | “Đề cương đã được tạo. Đây là chờ dữ liệu, không phải treo.” | Protocol và WAITING_USER_DATA |
| Về dashboard, mở bài khác rồi quay lại | “Bài chờ được lưu riêng. A/B/C chờ vẫn tạo D được, còn số bài chạy đồng thời có hạn mức riêng.” | Đề cương và trạng thái vẫn còn |
| Upload CSV khảo sát, điền các ô dưới đây | “Tệp được lưu cùng nguồn gốc. Dữ liệu người dùng cung cấp chưa được hệ thống xác minh độc lập.” | Tệp vừa upload được chọn đúng |
| Bấm tiếp tục | “Một job mới tiếp tục từ checkpoint đã lưu.” | Bài chuyển trạng thái/monitor cập nhật |
| Mở bản C đã hoàn tất nếu có | “Bài phải ghi rõ synthetic ở Abstract, Methods, Results và Conclusion.” | Thống kê, nhãn synthetic và giới hạn |

**Tệp:** [human-survey-synthetic.csv](../../examples/demo/human-survey-synthetic.csv). Không upload expected-checks.json để giả làm dữ liệu kết quả.

Điền các trường sau; cũng có trong [human-form-inputs.json](../../examples/demo/human-form-inputs.json). Chỉ upload file chưa tự resume: điền đủ rồi bấm tiếp tục.

**Cỡ mẫu / Sample size:** `24` — 24 dòng mô phỏng.

**Nguồn gốc / Data provenance:**

~~~text
Synthetic fixture generated by scripts/prepare-demo.py, supplied by the presenter solely to demonstrate upload, checkpoint resume and descriptive reporting. Not collected from university students. File checksum and computed statistics are in examples/demo/expected-checks.json.
~~~

**Phương pháp / Method notes:**

~~~text
SOFTWARE DEMONSTRATION ONLY. Twenty-four deterministic synthetic rows generated by scripts/prepare-demo.py. No real participants, recruitment, consent process or ethics approval. Descriptive cell arithmetic only; this is not a validated questionnaire or real fieldwork.
~~~

**Tóm tắt kết quả / Results summary:**

~~~text
SYNTHETIC DATA ONLY. There are 24 rows, no missing responses. Mean usefulness=3.5; sample SD=1.1420804814403216 (ddof=1). Mean verification effort=3.0; sample SD=1.4744195615489712 (ddof=1). Usefulness frequencies: 2:6, 3:6, 4:6, 5:6. Verification effort frequencies: 1:5, 2:5, 3:4, 4:5, 5:5. No inferential tests or causal conclusions. Check these against the uploaded CSV statistics.
~~~

**Lời giải thích:**

> Usefulness trung bình là 3.5, verification effort là 3.0. Đây là thống kê mô tả của file mô phỏng, không suy ra quan hệ nhân quả hoặc kết luận cho sinh viên thật. Không tự thêm p-value, phê duyệt đạo đức hay tuyển người chưa thực hiện.

Các mô tả nhập sẵn là để diễn tập form, phải đối chiếu với thống kê từ CSV. Khi dùng dữ liệu thật phải thay bằng thông tin thu thập đúng thực tế và đáp ứng yêu cầu đạo đức phù hợp.

## 8. Kết thúc — 1 phút

> Qua ba bài, em làm rõ ba kiểu bằng chứng: tài liệu đã công bố, số liệu do chương trình tính và dữ liệu người dùng cung cấp. Giá trị của Synthia là tổ chức các vai trò và bước xử lý thành quy trình theo dõi được, có thể dừng/tiếp tục và đối chiếu nguồn gốc.
>
> Đây là ứng dụng web chạy local cho bản demo. Có thể phát triển thành dịch vụ nội bộ cho doanh nghiệp, nhưng cần hoàn thiện thêm bảo mật, phân quyền và cách ly dữ liệu, quản lý khóa API, nhật ký kiểm toán, sao lưu, giám sát và nghiệm thu vận hành trước khi triển khai thật.
>
> Phạm vi hiện tại còn giới hạn: routine tính toán cố định, nội dung cần con người kiểm tra và API miễn phí có hạn mức. Kiểm thử phần mềm không chứng minh bài đạt chuẩn tạp chí; vòng Critic không thay phản biện độc lập. Hướng tiếp theo là đánh giá chất lượng có đối chứng và mở rộng thí nghiệm khi có môi trường chạy an toàn.

Nếu cần nêu số test: bản chốt có **1,013 backend passed, 90 frontend passed, CI 6/6**. Không nói mọi tình huống hoặc mọi model đã được kiểm hết. Ba lượt nghiệm thu mới gần nhất bị 429; chỉ thay thông tin này sau khi đã có lượt thực chạy thành công và đã đọc bài.

## 9. Khi bị hỏi hoặc demo có lỗi

| Câu hỏi/tình huống | Trả lời ngắn |
|---|---|
| 429 | “Provider giới hạn tốc độ/hạn mức. Em mở kết quả đã diễn tập trước nếu có; lượt live này chưa hoàn tất.” Không giả bảng offline là kết quả live |
| Chưa có bản thảo mới | Demo phần có bằng chứng: tạo bài, monitor, protocol, routine offline; nói rõ chưa chứng minh pipeline sinh bài mới hoàn chỉnh |
| NEEDS_REVIEW | Mở lý do, phân biệt bản thảo đã sinh với bản thảo đạt kiểm tra chất lượng |
| Sao không dùng chatbot? | Có phân vai, trạng thái, provenance, công cụ và vòng sửa; muốn khẳng định tốt hơn cần so sánh công bằng với single-agent |
| Agent là microservice riêng? | Không. Role/node trong LangGraph, API/worker là các tiến trình riêng của modular monolith |
| Có tự làm mọi nghiên cứu? | Không. Ba luồng là cách tổ chức; thực thi phụ thuộc dữ liệu, công cụ và routine hỗ trợ |
| Có loại hết bịa đặt? | Không. Có kiểm bằng chứng, tham chiếu và Critic; hỗ trợ ngữ nghĩa vẫn cần người rà soát |
| Free mà hiện USD? | Dự toán không phải hóa đơn. Phí thực phụ thuộc dịch vụ/model; không được âm thầm chuyển sang model trả phí |
| Tái lập nghĩa là đúng? | Không. Chạy lại khớp chưa chứng minh thiết kế đúng hoặc kết quả khái quát được |

## 10. Checklist diễn tập

- [ ] Docker, đăng nhập và địa chỉ 3082 hoạt động; model đã được thử bằng lượt gọi thực, không chỉ lưu key.
- [ ] Có ba câu hỏi, hai CSV chính và form khảo sát; biết upload đúng ô.
- [ ] Đã ghi URL bài thật, biết bài nào hoàn tất/chờ/cần xem lại.
- [ ] Có một bài C riêng còn chờ nếu muốn vừa demo resume vừa mở bản C hoàn tất.
- [ ] Đã đọc từng đầu ra, kiểm một claim/citation, số liệu và nhãn synthetic.
- [ ] Không lộ key/token, không gọi dữ liệu mô phỏng là khảo sát thật.
- [ ] Đã bấm giờ; thời lượng kịch bản là thời gian nói/thao tác, không phải tốc độ LLM.
