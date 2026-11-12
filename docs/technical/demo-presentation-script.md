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

### 4.5. Hướng dẫn luồng thao tác trên giao diện (UI User Journey)

Khi bắt đầu sử dụng hệ thống, người nghiên cứu thao tác theo các bước tuần tự trên giao diện web:

1. **Truy cập & Thiết lập cấu hình cá nhân:**
   - Mở trình duyệt vào `http://127.0.0.1:3082`.
   - Đăng nhập tài khoản cá nhân. Vào mục **Settings** ở thanh điều hướng trên cùng để quản lý thông tin hồ sơ và cấu hình API Key/Model (OpenAI, Gemini, OpenRouter...).
2. **Khởi tạo nghiên cứu mới (Home / Dashboard):**
   - Tại trang chủ, nhập câu hỏi nghiên cứu (Research Question / Topic) vào ô tìm kiếm trung tâm.
   - Nhấn vào nút **Research Configuration** (biểu tượng cấu hình) để mở hộp thoại thiết lập chuyên sâu:
     - **Chọn loại hình nghiên cứu (Study Mode):** Tổng quan tài liệu (`REVIEW`), Thực nghiệm tính toán (`EMPIRICAL_COMPUTATIONAL`), hoặc Khảo sát thực địa ngoài hệ thống (`EMPIRICAL_HUMAN`).
     - **Độ sâu nghiên cứu (Research Depth):** Fast (1 vòng nghiên cứu), Standard (2 vòng), hoặc Comprehensive (3 vòng).
     - **Độ dài bài báo & Phong cách trích dẫn:** Short, Medium, Long; Định dạng trích dẫn IEEE, APA hoặc Harvard.
     - **Tùy chọn phê duyệt đề cương (Human-in-the-Loop):** Tích chọn *Require Plan Approval* nếu muốn tự tay duyệt kế hoạch và câu truy vấn trước khi Agent tiến hành tìm kiếm.
     - **Nạp tài liệu PDF cá nhân (Private PDF Documents):** Cho phép tải lên tối đa 5 tệp PDF tài liệu tham khảo riêng (giới hạn 10 MiB) để hệ thống lập chỉ mục và ưu tiên trích dẫn.
     - **Cấu hình trần hạn mức (Shared Agent Allowance):** Tùy chỉnh số lượt gọi LLM tối đa (5–100 calls), trần token đầu vào/đầu ra và trần ngân sách USD dùng chung cho cả 7 Agent.
3. **Theo dõi tiến trình trực tiếp trong Workspace (`/research/[id]`):**
   - Sau khi bấm **Start Research**, hệ thống tự động điều hướng vào trang Workspace riêng của bài báo.
   - **Thanh tiến trình Workflow Pipeline (7 chặng):** Hiển thị rõ ràng giai đoạn đang chạy (Planning ➔ Literature Search ➔ Source Processing ➔ Evidence Analysis ➔ Drafting Paper ➔ AI Critique ➔ Citation Check).
   - **Bảng giám sát trực tiếp (Live Monitor):** Bấm nút **Open Live Monitor** (`/research/[id]/monitor`) để theo dõi chi tiết từng hành động của các Agent theo thời gian thực.
4. **Kiểm tra kết quả & Đối chiếu nguồn:**
   - Đọc bản thảo bài báo đầy đủ trong tab **Scientific Paper**.
   - Bấm vào bất kỳ trích dẫn nào trong bài để xem đối chiếu tức thời đoạn văn gốc tại tab **Sources** hoặc ma trận đối soát tại tab **Evidence & Citations**.
   - Xem kết quả chạy mô hình, số liệu sai số và biểu đồ phân tích trong tab **Experiments**.
   - Theo dõi chi phí và số token đã tiêu thụ của từng Agent trong tab **Agent Runs & Cost**.
5. **Xuất bản bài báo (Export):**
   - Bấm nút **Export** ở góc trên để tải về bài báo dưới dạng Microsoft Word (`.docx`), Markdown (`.md`), hoặc in bản PDF đã được format học thuật chuẩn mực.

---

### 4.6. Cấu trúc của một bài nghiên cứu hoàn chỉnh (Full Manuscript Structure)

Bản thảo do Synthia tạo ra không phải là một đoạn tóm tắt đơn giản, mà là một bài báo khoa học hoàn chỉnh tuân thủ cấu trúc học thuật quốc tế **IMRaD**:

1. **Title & Abstract:** Tiêu đề học thuật súc tích, phần tóm tắt nêu bật bài toán, phương pháp luận, kết quả chính lượng hóa và đóng góp của bài báo. Kèm danh sách từ khóa (Keywords).
2. **1. Introduction (Mở đầu & Định vị khoảng trống):**
   - Giới thiệu bối cảnh học thuật và thực tiễn của đề tài.
   - Nêu rõ bài toán trọng tâm, tính cấp thiết và động lực nghiên cứu.
   - **Định vị Research Gap (Khoảng trống nghiên cứu):** Chỉ ra những mâu thuẫn, hạn chế hoặc điểm chưa được giải quyết trong các nghiên cứu giai đoạn gần đây (2020–2025).
3. **2. Related Work / Background (Tổng quan tài liệu & Bằng chứng):**
   - Tổng hợp có hệ thống các công trình nghiên cứu tiền nhiệm.
   - Phân loại các trường phái nghiên cứu, so sánh ưu nhược điểm qua ma trận bằng chứng đối chứng.
4. **3. Methodology & Hypotheses (Phương pháp luận & Giả thuyết):**
   - Thiết kế nghiên cứu và quy trình thu thập dữ liệu / bằng chứng.
   - **Phát biểu Giả thuyết nghiên cứu ($H_0, H_1$):** Đưa ra các giả thuyết khoa học rõ ràng, có thể kiểm chứng được bằng dữ liệu hoặc bằng chứng thực nghiệm.
   - Mô tả tiêu chí chọn lọc (eligibility criteria), phương pháp phân tích số liệu hoặc thuật toán mô hình hóa.
5. **4. Experiments & Results / Findings (Thực nghiệm & Kết quả):**
   - **Thiết lập thực nghiệm:** Chi tiết về tập dữ liệu (dataset), chia train/test split, random seed đảm bảo tính tái lập (reproducibility).
   - **Bảng so sánh định lượng:** Bảng đối chuẩn kết quả giữa mô hình thực nghiệm với Baseline trung bình (đầy đủ các chỉ số đo lường như MAE, RMSE, $R^2$).
   - **Biểu đồ thực nghiệm (Figures):** Chèn trực tiếp các hình ảnh biểu đồ phân tán, biểu đồ phần dư được sinh ra từ code phân tích thực tế kèm chú thích (caption) học thuật chuẩn mực.
6. **5. Discussion (Thảo luận):**
   - Phân tích và lý giải ý nghĩa khoa học của các kết quả vừa đạt được.
   - Đối chiếu với các phát hiện của các tác giả trước đó để làm rõ kết quả này củng cố hay phản bác quan điểm nào.
7. **6. Limitations & Threats to Validity (Hạn chế của nghiên cứu):**
   - Thẳng thắn chỉ ra các giới hạn về mặt dữ liệu (cỡ mẫu, tính đại diện), giới hạn của thuật toán và các yếu tố ngoại cảnh có thể ảnh hưởng đến kết luận.
8. **7. Conclusion & Future Work (Kết luận & Hướng phát triển):**
   - Đúc kết ngắn gọn các phát hiện cốt lõi và đề xuất các hướng nghiên cứu mở rộng trong tương lai.
9. **References (Danh mục tài liệu tham khảo):**
   - Danh sách nguồn trích dẫn được chuẩn hóa tự động theo định dạng yêu cầu (IEEE, APA, Harvard).
   - Từng tài liệu tham khảo đều có liên kết đối chiếu với các đoạn trích dẫn thực tế trong bài, không bịa đặt nguồn ma.

---

### 4.7. Cơ chế tìm Research Gap, Đặt giả thuyết & Sinh đề cương thực nghiệm

Một trong những năng lực học thuật quan trọng nhất của hệ thống là khả năng suy luận khoa học theo quy trình:

1. **Cơ chế tìm Research Gap (Khoảng trống nghiên cứu):**
   - Tác tử **Researcher** thu thập các bài báo khoa học mới nhất xoay quanh câu hỏi nghiên cứu.
   - Tác tử **Evidence Analyst** đọc sâu nội dung các nghiên cứu và lập ma trận so sánh chéo. Tác tử này được trang bị chỉ dẫn chuyên biệt để phát hiện **điểm mâu thuẫn (Contradictions)** giữa các nghiên cứu (ví dụ: công trình A kết luận phương pháp X vượt trội, nhưng công trình B lại chỉ ra phương pháp X suy giảm độ chính xác khi áp dụng trên tập dữ liệu đa biến).
   - Từ các bất đồng quan điểm và các giới hạn chưa được khảo sát, tác tử **Supervisor** tổng hợp và định vị chính xác **Research Gap** cần giải quyết.
2. **Cơ chế phát biểu Giả thuyết nghiên cứu ($H_0, H_1$):**
   - Dựa trên Research Gap đã định vị, hệ thống tự động xây dựng các cặp giả thuyết khoa học:
     - **Giả thuyết không ($H_0$ - Null Hypothesis):** Khẳng định không có sự khác biệt có ý nghĩa thống kê hoặc phương pháp đề xuất không cải thiện hiệu năng so với baseline mặc định.
     - **Giả thuyết đối ($H_1$ - Alternative Hypothesis):** Khẳng định phương pháp hoặc mô hình đề xuất tạo ra sự khác biệt hoặc giảm thiểu sai số có ý nghĩa trên tập dữ liệu kiểm nghiệm.
3. **Sinh đề cương thực nghiệm (Protocol Generation):**
   - Hệ thống tự động tạo ra một **Research Protocol** chuẩn hóa dưới định dạng JSON/Markdown quy định:
     - Biến độc lập (Independent variables), biến phụ thuộc (Dependent variables / Target).
     - Quy trình tiền xử lý dữ liệu (chỉ chuẩn hóa trên tập train, tránh rò rỉ dữ liệu - data leakage).
     - Baseline so sánh được chỉ định rõ ràng.
     - Metrics đánh giá mục tiêu và routine tính toán tương ứng cần gọi.

---

### 4.8. Cơ chế chạy thí nghiệm thực tế & Tự động sinh biểu đồ

Hệ thống trả lời dứt khoát câu hỏi: **"Hệ thống có chạy thí nghiệm thật không, hay AI tự tưởng tượng ra số liệu?"**

- **CHẠY THÍ NGHIỆM THẬT (Không sinh số liệu giả):**
  - Ở luồng **EMPIRICAL_COMPUTATIONAL**, hệ thống **hoàn toàn không để LLM tự đoán hay tự viết số đo**.
  - Khi người dùng tải lên tập dữ liệu thực nghiệm (file CSV, ví dụ: dữ liệu tiêu thụ điện năng 120 dòng), worker Celery sẽ kích hoạt một **routine phân tích tính toán Python độc lập** (sử dụng thư viện chuẩn `scikit-learn`, `numpy`, `pandas`).
  - Routine này chạy trên môi trường thực tế:
    - Chia tập dữ liệu cố định với random seed kiểm soát (ví dụ: seed 42, 96 dòng train và 24 dòng test).
    - Tính toán Baseline (dự đoán bằng trung bình tập train).
    - Huấn luyện mô hình thực nghiệm (ví dụ: Ridge Regression với tham số $\alpha = 1.0$).
    - Đo lường sai số thực tế trên tập kiểm nghiệm held-out: MAE, RMSE, $R^2$.
- **Cơ chế tự động sinh và chèn biểu đồ (Figure Generation):**
  - Trong quá trình chạy routine tính toán, mã nguồn Python tự động gọi `matplotlib.pyplot` và `seaborn` để vẽ các biểu đồ phân tích trực quan:
    - **Biểu đồ phân tán (Scatter Plot):** Thể hiện tương quan giữa giá trị thực tế (Ground Truth) và giá trị mô hình dự đoán (Predicted), kèm đường tham chiếu lý tưởng $y = x$.
    - **Biểu đồ phân phối phần dư (Residual Plot):** Trực quan hóa sai số dự đoán để đánh giá tính chuẩn tắc và hiện tượng phương sai thay đổi (heteroscedasticity).
    - **Biểu đồ cột so sánh sai số:** So sánh trực diện sai số MAE và RMSE giữa Baseline và Mô hình đề xuất.
  - Các biểu đồ được lưu bền vững thành tệp ảnh chất lượng cao trong hệ thống lưu trữ artifact (`/storage/artifacts/{task_id}/figure_{n}.png`).
  - Tác tử **Writer** sau đó tự động nhúng các hình ảnh này vào đúng vị trí trong mục Results của bản thảo bằng cú pháp markdown học thuật:
    `![Figure 1: Comparison of Actual vs Predicted Values](/api/v1/research/{task_id}/figures/figure_1.png)`
    đồng thời viết đoạn văn phân tích, diễn giải các xu hướng định lượng được thể hiện trên biểu đồ.

---

### 4.9. Thu nạp tài liệu cá nhân, Giám sát thời gian thực & Lưu Log kiểm toán

1. **Thu nạp tài liệu & Dữ liệu do người dùng cung cấp (Private Ingestion):**
   - **Tải lên PDF cá nhân:** Ngay tại màn hình tạo bài, người dùng có thể đính kèm các tài liệu nghiên cứu nội bộ hoặc tài liệu chuyên ngành chưa công bố (tối đa 5 file PDF, 10 MiB).
   - **Xử lý trích xuất & Vector Embeddings:** Tác tử **Curator** sử dụng bộ bóc tách văn bản, làm sạch cấu trúc, băm nhỏ thành các đoạn có ngữ cảnh (chunking 1024 ký tự kèm overlap 128 ký tự). Sau đó gọi model embedding để tạo vector và lưu vào `pgvector` trong PostgreSQL.
   - **Ưu tiên trích dẫn:** Khi Agent tìm kiếm bằng chứng, các đoạn tài liệu từ file PDF của người dùng được tìm kiếm theo độ tương đồng ngữ nghĩa (Cosine Similarity) và được ưu tiên đưa vào ma trận bằng chứng có gắn nhãn nguồn riêng.
2. **Giám sát từng bước theo thời gian thực (Step-by-step Monitoring):**
   - **Giao diện Pipeline 7 bước:** Phản ánh trực quan trạng thái từng tác tử (Xanh lá: Hoàn tất; Xanh dương nhấp nháy: Đang xử lý; Vàng cam: Đang chờ duyệt kế hoạch hoặc chờ nạp dữ liệu).
   - **Bảng Agent Monitor (`/research/[id]/monitor`):**
     - Hiển thị nhật ký thời gian thực theo từng sự kiện của Agent.
     - Cho phép mở xem chi tiết: Input payload, Output sinh ra ở từng bước, mô hình LLM đảm nhiệm, thời gian thực thi (latency), lượng token tiêu thụ và chi phí tương ứng.
     - Hiển thị quyết định rẽ nhánh của tác tử Critic (chấp thuận đi tiếp hay yêu cầu viết lại).
3. **Kiến trúc lưu trữ Log, Checkpoint & Nhật ký kiểm toán (Audit Ledger):**
   - **Log vận hành kỹ thuật:** Ghi nhận có cấu trúc qua module `logging` của Python và nhật ký worker Celery; hỗ trợ gán correlation ID để theo dõi vết lỗi xuyên suốt từ frontend đến worker.
   - **Nhật ký kiểm toán tài nguyên bền vững (Audit Ledger trong PostgreSQL):**
     - Bảng `research_tasks`: Lưu trữ trạng thái tổng thể và trường JSONB `budget_config` chứa thông tin chi tiết từng token input/output, số lượt gọi và số USD đã tiêu thụ theo thời gian thực.
     - Bảng `agent_runs`: Lưu trữ lịch sử từng lần gọi của từng Agent phục vụ kiểm toán minh bạch và đánh giá hiệu năng mô hình.
     - Bảng `workflow_runs`: Lưu lại lịch sử các phiên chạy và phiên bản bản thảo.
   - **Cơ chế Checkpoint bền bỉ (Durable State Checkpoint):**
     - Toàn bộ trạng thái của đồ thị tác tử `ResearchState` được tuần tự hóa và lưu trữ liên tục vào PostgreSQL sau mỗi node xử lý thông qua cơ chế Checkpointer của LangGraph.
     - Nếu worker bị khởi động lại, mạng bị ngắt hoặc bài bị tạm dừng do chạm trần chi phí, tiến trình nghiên cứu **không bao giờ bị mất**. Khi người dùng bấm duyệt tiếp tục, worker sẽ khôi phục chính xác trạng thái từ checkpoint và tiếp tục luồng công việc từ đúng vị trí dang dở.

---

### 4.10. Lời nói dẫn dắt của người trình bày (1–2 phút)

> *"Điểm khác biệt cốt lõi của Synthia so với một chatbot hay một AI agent đơn lẻ nằm ở 3 yếu tố: **cơ chế tự chủ theo mục tiêu**, **sự chuyên môn hóa thành 7 tác tử độc lập**, và **vòng lặp kiểm chứng chéo chặt chẽ**.*
>
> *Quy trình bắt đầu ngay từ giao diện trực quan: người dùng nhập đề tài, có thể tải lên tài liệu PDF cá nhân để nạp vào cơ sở tri thức vector pgvector và cấu hình hạn mức an toàn. Toàn bộ tiến trình được theo dõi minh bạch qua thanh Pipeline 7 chặng và bảng Live Monitor.*
>
> *Thay vì để AI tự bịa số liệu, ở các bài thực nghiệm, Synthia kích hoạt routine Python chạy tính toán thật trên dữ liệu, đo lường chính xác các chỉ số sai số MAE, RMSE, R² và tự động vẽ biểu đồ trực quan để nhúng vào bài báo. Đặc biệt, hệ thống phát hiện Research Gap từ các mâu thuẫn học thuật, tự phát biểu giả thuyết khoa học H0/H1 và soạn thảo bản thảo hoàn chỉnh theo chuẩn quốc tế IMRaD.*
>
> *Toàn bộ dữ liệu, lịch sử gọi của Agent và checkpoint được lưu bền vững trong PostgreSQL, đảm bảo bài nghiên cứu có thể dừng và tiếp tục an toàn mà không bao giờ mất dữ liệu."*

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
| Có chạy thí nghiệm thật không? | Có. Ở luồng tính toán, worker chạy code Python thực tế (Scikit-learn, Pandas), đo MAE/RMSE/R² thật và vẽ biểu đồ, không để LLM bịa số liệu |
| Sinh biểu đồ như thế nào? | Routine Python tự động gọi Matplotlib/Seaborn xuất ảnh PNG vào artifact storage và Writer nhúng trực tiếp vào mục Results kèm caption học thuật |
| Làm sao tìm Research Gap & đặt giả thuyết? | Evidence Analyst đối chiếu các nghiên cứu tìm điểm mâu thuẫn để định vị Gap; Supervisor xây dựng cặp giả thuyết H0/H1 và protocol thực nghiệm |
| Giám sát từng bước và lưu log thế nào? | Giao diện có Pipeline 7 chặng và Live Monitor xem input/output từng Agent; hệ thống lưu audit log, token/cost và checkpoint bền vững trong PostgreSQL |

## 10. Checklist diễn tập

- [ ] Docker, đăng nhập và địa chỉ 3082 hoạt động; model đã được thử bằng lượt gọi thực, không chỉ lưu key.
- [ ] Có ba câu hỏi, hai CSV chính và form khảo sát; biết upload đúng ô.
- [ ] Đã ghi URL bài thật, biết bài nào hoàn tất/chờ/cần xem lại.
- [ ] Có một bài C riêng còn chờ nếu muốn vừa demo resume vừa mở bản C hoàn tất.
- [ ] Đã đọc từng đầu ra, kiểm một claim/citation, số liệu và nhãn synthetic.
- [ ] Không lộ key/token, không gọi dữ liệu mô phỏng là khảo sát thật.
- [ ] Đã bấm giờ; thời lượng kịch bản là thời gian nói/thao tác, không phải tốc độ LLM.
