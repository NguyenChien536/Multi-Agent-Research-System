# Hướng dẫn demo Synthia

Cập nhật **05/11/2026**. Đọc tài liệu này để hiểu sản phẩm và diễn tập. Khi trình bày, mở [Kịch bản thuyết trình](demo-presentation-script.md): có lời nói, ba câu hỏi và từng bước thao tác.

## 1. Vấn đề và mục tiêu

**Synthia hỗ trợ người nghiên cứu từ câu hỏi đến bản thảo bài báo có nguồn và bằng chứng.** Các vai trò AI phối hợp để lập kế hoạch, tìm nguồn, phân tích, thiết kế phương pháp khi cần, viết và phản biện.

Khó khăn không chỉ là viết đủ Abstract, Introduction hay Conclusion. Người nghiên cứu phải biết kết luận dựa vào đâu, số liệu đã thực sự được đo chưa và còn giới hạn gì. Nếu yêu cầu AI viết ngay, những điều dự kiến làm dễ bị trình bày như kết quả đã chứng minh.

Synthia tổ chức những công việc này thành quy trình có trạng thái, dữ liệu riêng cho từng bài và màn hình theo dõi. Đầu ra là **bản thảo để người nghiên cứu kiểm tra và hoàn thiện**, không phải bảo đảm được nhận đăng.

## 2. Vì sao có ba loại nghiên cứu?

**Vì có ba cách tạo bằng chứng khác nhau:** đọc công trình đã có, chạy phép thử bằng máy tính và để con người thu thập dữ liệu. Không thể dùng một luồng viết bài cho tất cả: khi chưa làm thí nghiệm hoặc khảo sát thì chưa được tự viết Results như đã có kết quả.

Đây là ba **luồng xử lý chính của sản phẩm**, không phải cách phân loại đầy đủ mọi phương pháp khoa học và cũng không phải ba ngành nghiên cứu riêng biệt.

| Luồng | Hiểu đơn giản | Người dùng đưa vào | Hệ thống làm gì? | Đầu ra |
|---|---|---|---|---|
| **1. Tổng quan tài liệu — Literature Review** | Đọc nghiên cứu trước để hiểu đã biết gì, còn bất đồng hoặc thiếu gì | Câu hỏi; PDF riêng nếu có | Tìm tài liệu, trích bằng chứng, so sánh và tổng hợp | Bản thảo tổng quan có phạm vi tìm kiếm, tổng hợp theo chủ đề, thảo luận, giới hạn và References |
| **2. Thực nghiệm tính toán — Computational Study** | Chạy một phép thử để biết kết quả thực tế trên dữ liệu | Câu hỏi phù hợp và CSV số | Chạy routine được hỗ trợ, so với baseline, lưu số liệu, hình và nhật ký | Bản thảo thực nghiệm cùng kết quả chạy và thông tin chạy lại |
| **3. Nghiên cứu ngoài hệ thống — Human/External Study** | Có dữ liệu mà con người phải đi khảo sát, làm lab hoặc đo đạc | Câu hỏi; sau đó tệp kết quả và nguồn gốc dữ liệu | Soạn đề cương, dừng chờ; khi nhận dữ liệu thì tiếp tục | Trước khi có dữ liệu: đề cương. Sau khi nhận và xử lý thành công: bản thảo thực nghiệm |

**Ví dụ dễ nhớ:** đọc nghiên cứu về cách học → tổng quan; thử mô hình dự đoán từ CSV → tính toán; hỏi sinh viên về trải nghiệm sử dụng AI → khảo sát.

**Giới hạn hiện tại:** tổng quan demo là narrative review có phản biện, không tự nhận systematic review/PRISMA đầy đủ. Tính toán demo chạy routine Ridge so với baseline trung bình trên CSV số, không chạy mọi code AI tùy ý. Luồng ngoài hệ thống không thay con người tuyển người tham gia/làm lab; chưa có dữ liệu thì phải chờ.

## 3. Mở đúng bản demo

Mở Docker Desktop rồi mở terminal tại thư mục gốc dự án:

~~~powershell
.\scripts\release.ps1 -Action start
~~~

Đợi `Release ready`, mở **http://127.0.0.1:3082**. Nhóm Docker dùng để demo là **synthia-workflow-check**; các nhóm test/restore cứ để tắt. Chỉ có một cấu hình chính: `docker-compose.yml`. `migrate-1` chạy xong rồi dừng là bình thường.

Lệnh `start` chỉ bật image đã chốt, không build source đang sửa. Đưa code mới sang demo phải test, commit rồi dùng `release.ps1 -Action deploy`. Dev chạy bằng `dev.ps1 -Action start` ở cổng 3000, với dữ liệu và Settings riêng. Xem [cách dùng hai môi trường](local-release.md).

Đăng nhập → **Settings → API & model → Mặc định cho bài mới** → chọn dịch vụ, nhập key và model → **Lưu kết nối**. Không quay màn hình lúc nhập key. Bài mới tự dùng cấu hình đã lưu. Lưu thành công chưa chứng minh provider còn quota.

Đổi một bài hiện có qua Settings của bài khi bài không chạy/không ở hàng đợi. Đổi mặc định không tự đổi các bài cũ và không đặt lại lượng sử dụng đã ghi. API miễn phí vẫn có giới hạn tốc độ/hạn mức.

**Sửa hồ sơ:** Settings → **Thông tin cá nhân → Chỉnh sửa**. Bấm **Lưu thay đổi** mới cập nhật; **Hủy** bỏ các thay đổi chưa lưu. Đổi email cần mật khẩu hiện tại; lần đăng nhập sau dùng email mới. Thanh bên cập nhật ngay sau khi lưu. **Xóa tài khoản** cần mật khẩu và nhập `DELETE`; chỉ thử bằng tài khoản demo riêng vì xác nhận sẽ khóa tài khoản ngay và xóa bài/file ở nền.

## 4. Bộ ba bài đã chuẩn bị

Các file dưới đây nằm trong `examples/demo/`. Câu hỏi tiếng Anh có thể copy nguyên văn; phần giải thích tiếng Việt giúp bạn trình bày.

| Bài | Đề tài | Câu hỏi | Input cần tải lên |
|---|---|---|---|
| **A — Tổng quan** | Luyện tập giãn cách và ghi nhớ dài hạn | [review-question.txt](../../examples/demo/review-question.txt) | Không bắt buộc; PDF nguồn riêng là tùy chọn |
| **B — Tính toán** | Ridge có giảm sai số dự đoán điện năng so với trung bình không? | [computational-question.txt](../../examples/demo/computational-question.txt) | [CSV điện năng](../../examples/demo/computational-electricity-synthetic.csv) |
| **C — Khảo sát** | Mức hữu ích và công sức kiểm chứng khi dùng trợ lý AI | [human-question.txt](../../examples/demo/human-question.txt) | [CSV khảo sát](../../examples/demo/human-survey-synthetic.csv) và [các ô nhập mẫu](../../examples/demo/human-form-inputs.json) |

**Synthetic = dữ liệu mô phỏng**, không phải điện năng đo thực hoặc phản hồi của người thật.

Cấu hình diễn tập: **STANDARD**, **MEDIUM**, **English**, tối đa **12 nguồn**, **2 vòng**; APA cho A/C, IEEE cho B. Đây là cấu hình gợi ý, không bảo đảm model miễn phí đủ quota. Nguồn tối đa là giới hạn thu thập, không phải số nguồn chắc chắn được trích.

### A. Tổng quan: từ nguồn đến lập luận

1. Chọn **Tổng quan / REVIEW**, dán câu hỏi A; bật **Duyệt kế hoạch**.
2. Khi kế hoạch xuất hiện, đọc phạm vi/truy vấn và duyệt, hoặc yêu cầu sửa trước khi duyệt.
3. Mở **Agent Monitor / Giám sát Agent**, xem bước và kết quả từng vai trò.
4. Khi có bài, mở **Bài báo → Nguồn → Bằng chứng & Trích dẫn**. Chọn một claim và đối chiếu với đoạn nguồn.
5. Kiểm mục con, tổng hợp theo chủ đề, nghiên cứu khác nhau và giới hạn. Không chỉ kiểm bài có đủ các tiêu đề lớn.

**Điều cần chứng minh:** có quy trình tìm nguồn và lập luận có thể đối chiếu, không chỉ sinh một đoạn văn dài. Citation hợp lệ không bảo đảm hỗ trợ ngữ nghĩa hoàn toàn.

### B. Tính toán: từ CSV đến kết quả thực chạy

1. Chọn **Tính toán / EMPIRICAL_COMPUTATIONAL**, dán câu hỏi B. Có thể tắt duyệt kế hoạch để tiết kiệm thời gian nói.
2. Khi yêu cầu dữ liệu, mở **Experiments / Thực nghiệm**, upload đúng CSV điện năng vào ô dataset; không dùng ô PDF hay kết quả khảo sát.
3. Nếu đang `WAITING_USER_DATA`, upload dataset sẽ tự xếp hàng tiếp tục; không bấm Start lần hai.
4. Khi xong, xem thí nghiệm, bảng chỉ số, hình, journal và gói chạy lại nếu có. Kiểm số liệu trong bài khớp runner.

CSV có **120 dòng**, đầu vào `temperature`, `occupied_hours`, cột đích `target`. Routine cố định: seed 42, train 96/test 24, Ridge alpha=1, chuẩn hóa chỉ fit trên train. Baseline là cách đơn giản: luôn dự đoán trung bình của dữ liệu train.

**Đối chiếu từ lần kiểm offline trên đúng file mẫu; không phải một lượt web vừa hoàn tất:**

| Chỉ số | Baseline | Ridge | Cách hiểu |
|---|---:|---:|---|
| MAE | 12.338741 | 1.335145 | Sai số tuyệt đối trung bình; nhỏ hơn tốt hơn |
| RMSE | 14.210697 | 1.468646 | Nhấn mạnh lỗi lớn; nhỏ hơn tốt hơn |
| R² | -0.012568 | 0.989185 | So độ khớp với mốc trung bình trên test; có thể âm |

**Điều cần chứng minh:** phép thử có baseline, dữ liệu và cấu hình để kiểm lại. Chỉ kết luận trên bộ dữ liệu/split đã chạy; không suy ra mô hình tốt nhất, tốt trên dữ liệu thật hoặc có ý nghĩa thống kê.

Nếu còn thời gian, thử [CSV negative control](../../examples/demo/computational-negative-control-synthetic.csv) trên task khác. Hai features hằng số; kiểm offline cho `NO_IMPROVEMENT`, delta MAE=0. Giữ kết quả không cải thiện cũng là một phần của nghiên cứu.

### C. Khảo sát: có thể chờ và tiếp tục

1. Chọn **Thực địa/Khảo sát / EMPIRICAL_HUMAN**, dán câu hỏi C.
2. Khi `WAITING_USER_DATA`, mở/tải **đề cương**. Giải thích đây là chờ dữ liệu, không phải treo.
3. Về dashboard mở bài khác rồi quay lại: bài C vẫn giữ trạng thái/đề cương. A/B/C cùng chờ vẫn có thể tạo D; số bài đang chạy đồng thời có hạn mức riêng, mặc định 2/user.
4. Upload CSV khảo sát vào **Tệp kết quả thực địa**, chọn tệp vừa upload và điền từ `human-form-inputs.json`: cỡ mẫu, nguồn gốc, phương pháp, tóm tắt kết quả. **Cỡ mẫu = 24 dòng mô phỏng**, không phải 24 người thật.
5. Điền đủ rồi bấm **Tiếp tục**. Khác luồng tính toán, chỉ upload file khảo sát chưa tự resume.
6. Kiểm bản thảo nói rõ synthetic ở Abstract, Methods, Results và Conclusion. Không được tự thêm tuyển người, phê duyệt đạo đức, p-value hoặc nhân quả.

Đối chiếu: usefulness mean=**3.5**, sample SD=**1.142080**; verification effort mean=**3.0**, sample SD=**1.474420**. Sample SD dùng n−1 (ddof=1). `synthetic_response_id` chỉ là ID, không diễn giải như thang đo.

**Điều cần chứng minh:** dừng/tiếp tục đúng bài, lưu nguồn gốc và không bịa Results. Intake hiện hỗ trợ CSV/TXT và thống kê mô tả CSV, không phải mọi định dạng lab/SPSS.

## 5. Chuẩn bị và xử lý khi demo

| Chuẩn bị | Cách làm |
|---|---|
| Ba bài đã diễn tập | Chạy lần lượt A/B/C, đọc đầu ra, ghi URL riêng không chứa key; thời gian provider không cố định |
| Bài C còn chờ | Giữ một task riêng chờ dữ liệu nếu muốn vừa demo resume vừa có một task C khác đã hoàn tất |
| Dự phòng | Mở kết quả đã chạy thật hoặc file tải từ hệ thống. Nói rõ chạy trước, không giả làm vừa sinh tức thì |
| Kiểm bài | Mục con hợp lý, claim có căn cứ, References khớp, hình có giải thích, số liệu khớp, giới hạn rõ |
| Bảo mật khi trình bày | Không mở API key, token hoặc private.env trước khán giả |

| Trạng thái/lỗi | Ý nghĩa và cách xử lý |
|---|---|
| `QUEUED` | Chờ worker nhận. Nếu kéo dài, kiểm worker/dispatcher và monitor |
| `RUNNING` | Đang xử lý; xem bước mới nhất trong monitor |
| `WAITING_APPROVAL` | Cần duyệt/sửa kế hoạch |
| `WAITING_USER_DATA` | Cần dataset hoặc dữ liệu khảo sát, upload đúng ô |
| `NEEDS_REVIEW` / `PARTIAL` | Có thể có bản thảo nhưng còn thiếu sót; đọc lý do, không coi là đã đạt |
| `FAILED` | Lỗi làm gián đoạn; đọc thông báo trước khi chạy lại |
| 429 | Provider giới hạn tốc độ/hạn mức. Chờ hoặc cấu hình dịch vụ/model còn quota; không retry liên tục |
| Thiếu bằng chứng | Bổ sung nguồn/kết quả, không yêu cầu Writer tự lấp chỗ trống |
| Hết budget/token | Đổi model không reset lượng sử dụng; có thể cần task mới với cấu hình phù hợp |

## 6. Hiểu code để trả lời thầy

**Một lần bấm bắt đầu:** Next.js gửi yêu cầu → FastAPI kiểm người dùng và lưu bài → outbox lưu ý định gửi việc → Redis chuyển job → Celery worker chạy LangGraph → agent dùng nguồn/công cụ → PostgreSQL và kho file lưu kết quả → giao diện đọc qua API. Bản hiện tại có polling; không giới thiệu SSE replay là đã nghiệm thu.

| Thành phần | Hiểu đơn giản | Nơi đọc code |
|---|---|---|
| Next.js / React | Giao diện, tạo bài, đọc bài và monitor | `frontend/src/app/`, `frontend/src/lib/api.ts` |
| FastAPI / Pydantic | API, xác thực và kiểm dữ liệu | `backend/app/api/v1/`, `backend/app/schemas/` |
| PostgreSQL / SQLAlchemy | Lưu bài, nguồn, trạng thái và phiên bản | `backend/app/models/`, `backend/alembic/versions/` |
| Redis / Celery | Gửi và chạy việc dài ở nền | `backend/app/services/task_dispatcher.py`, `backend/app/worker.py` |
| LangGraph | Chuyển bước, vòng lặp, dừng và tiếp tục | `backend/app/agents/graph.py`, `state.py`, `nodes.py` |
| Runner / intake | Tính baseline/Ridge và kiểm dữ liệu khảo sát | `backend/app/services/experiment_runner.py`, `isolated_experiment.py`, `fieldwork_intake.py` |
| API/model Settings | Lưu khóa mã hóa và cấu hình mặc định/riêng | `backend/app/services/user_model_settings.py`, `model_connection.py` |

**Năm role cốt lõi:** Supervisor lập kế hoạch → Researcher tìm nguồn → Evidence Analyst phân tích → Writer viết → Critic phản biện. Methodologist và nhánh thực nghiệm dùng khi cần. Curator, validators và runner có phần xử lý bằng code; không phải mọi module đều là LLM agent.

Critic có thể yêu cầu Writer sửa hoặc quay lại tìm nguồn. Hai vòng đều có giới hạn. Critic là kiểm tra nội bộ, không phải peer review độc lập.

Kiến trúc là **modular monolith**, API/worker chạy thành các tiến trình riêng; không tách từng agent thành microservice. Pattern chính: graph/state machine, transactional outbox, worker claim chống chạy lặp, dependency injection và provider adapter. Không hứa exactly-once toàn hệ thống hay loại hết hallucination.

Dùng VS Code để đọc/debug code; Antigravity khi muốn AI hỗ trợ sửa. Cùng một thư mục dự án, không cần tạo bản sao. Tránh để hai công cụ cùng sửa một file.

## 7. Trạng thái kiểm chứng

Bản chốt ngày 05/11: commit `068b532876e8`, branch `feature/89-demo-workflow`, draft PR #109 vào develop. Backend **701 passed, 3 skipped**; frontend **34 passed**; CI **6/6 thành công**. Đây là kết quả của bản chốt, không thay kiểm thử sau thay đổi code mới.

Bộ fixture đã kiểm offline: routine baseline/Ridge, chạy lại cùng cấu hình và intake khảo sát. Tạo lại bằng môi trường Python dự án, không gọi provider:

~~~powershell
.\.venv\Scripts\python.exe scripts/prepare-demo.py
~~~

**Ba lượt nghiệm thu mới gần nhất bị 429 tại Supervisor, chưa tạo được bài mới được nghiệm thu.** Số test và bảng offline không chứng minh pipeline UI/provider đã chạy trọn ba bài hoặc đạt chất lượng xuất bản/Q1. Chỉ gọi bài demo sẵn sàng sau khi đã mở và kiểm đầu ra thật.

Sau buổi trình bày, dừng dịch vụ và giữ dữ liệu:

~~~powershell
.\scripts\release.ps1 -Action stop
~~~

Không chạy `down -v`, không xóa volume và không thay APP_SECRET_KEY của môi trường đang giữ API key mã hóa.
