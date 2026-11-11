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

## 4. Synthia khác gì chatbot và một AI agent? — 1–2 phút

**Hiển thị:** sơ đồ kiến trúc và Agent Monitor. Nếu cần, dùng bảng dưới đây làm slide so sánh.

| Tiêu chí | Chatbot | Một AI agent | Synthia — Multi-Agent Research System |
|---|---|---|---|
| Cách làm việc | Chủ yếu trao đổi theo từng yêu cầu; khả năng dùng công cụ tùy sản phẩm và cấu hình | Nhận mục tiêu, một agent có thể tự lập kế hoạch và gọi công cụ | Quy trình nghiên cứu chia thành các vai trò chuyên biệt, được LangGraph điều phối theo trạng thái |
| Vai trò trong dự án | Không mặc định có quy trình nghiên cứu và hồ sơ nguồn của riêng bài | Một agent có thể tìm, phân tích và viết trong cùng một luồng | Supervisor lập kế hoạch; Researcher tìm nguồn; Evidence Analyst phân tích bằng chứng; Writer soạn; Critic rà soát |
| Theo dõi và truy xuất | Tùy sản phẩm; hội thoại không tự đảm bảo lưu nguồn và bằng chứng theo từng bài | Có thể lưu trạng thái nếu được thiết kế | Lưu trạng thái bài, nguồn, bằng chứng và tiến trình để người dùng kiểm tra |
| Kiểm tra | Có thể được yêu cầu tự kiểm tra, nhưng mức kiểm tra tùy cách dùng | Có thể có bước tự rà soát | Có Critic và các validator có quy tắc; vòng sửa có giới hạn. Đây vẫn là kiểm tra nội bộ, không phải bình duyệt độc lập |
| Đánh đổi | Nhanh và đơn giản, nhưng người dùng thường phải tự tổ chức các bước nghiên cứu | Ít thành phần hơn; một agent phải đảm nhiệm nhiều việc | Quy trình dễ theo dõi và chia vai hơn, nhưng tốn thêm lượt gọi, thời gian và có thêm điểm có thể lỗi |

**Lời nói:**

> Supervisor lập kế hoạch, Researcher tìm nguồn, Evidence Analyst phân tích bằng chứng, Writer viết và Critic kiểm tra để yêu cầu sửa hoặc bổ sung nguồn. Khi cần thực nghiệm thì có thêm bước thiết kế phương pháp và xử lý dữ liệu.
>
> Các vai trò không tự do tự giao việc cho nhau. Luồng và điều kiện chuyển bước được định nghĩa trong workflow LangGraph; các agent phối hợp qua trạng thái chung. Công việc dài chạy ở Celery worker nên giao diện không giữ một HTTP request trong suốt quá trình. PostgreSQL lưu bài, nguồn, trạng thái và phiên bản; giao diện theo dõi qua API.
>
> Điểm khác biệt cốt lõi của Synthia là quy trình có mục tiêu, phân vai, trạng thái dùng chung, truy xuất bằng chứng và vòng rà soát có giới hạn — chứ không phải khẳng định rằng nhiều agent luôn tốt hơn một agent. Một agent đơn lẻ cũng có thể dùng công cụ hoặc tự rà soát. Dự án chưa có đánh giá đối chứng chứng minh Synthia viết tốt hơn chatbot hay single-agent, và Critic không bảo đảm loại hết lỗi.

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

Nếu cần nêu số test: bản chốt `068b532876e8` có **701 backend passed/3 skipped, 34 frontend passed, CI 6/6**. Không nói mọi tình huống hoặc mọi model đã được kiểm hết. Ba lượt nghiệm thu mới gần nhất bị 429; chỉ thay thông tin này sau khi đã có lượt thực chạy thành công và đã đọc bài.

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
