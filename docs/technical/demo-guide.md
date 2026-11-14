# Hướng dẫn demo Synthia

Cập nhật **10/11/2026**. Đọc tài liệu này để hiểu sản phẩm và diễn tập. Khi trình bày, mở [Kịch bản thuyết trình](demo-presentation-script.md): có lời nói, ba câu hỏi và từng bước thao tác.

## Phương án demo ngày 10/11: chuẩn bị trước, trình diễn kết quả đã lưu

**Phần chính dùng kết quả đã chạy thật và được lưu trong ứng dụng.** Tạo bài ngay trước hội đồng chỉ là phần bổ sung: model miễn phí vẫn có thể quá tải, hết hạn mức hoặc trả kết quả sai định dạng. Sang ngày mới không có nghĩa mọi dịch vụ đã reset quota; thời điểm reset phụ thuộc provider. Hạn mức của từng bài trong Synthia cũng không tự reset theo ngày.

### Trước buổi demo

1. Bật bản demo ở cổng 3082, đăng nhập đúng tài khoản và kiểm tra database/worker hoạt động. Giữ bản release hiện tại; không build, nâng cấp Docker hoặc đổi model sát giờ trình bày.
2. Chọn ba bài ứng với REVIEW, EMPIRICAL_COMPUTATIONAL và EMPIRICAL_HUMAN. Ưu tiên kiểm tra bài đã có trước khi dùng quota để tạo lại. Chạy mới thì chạy lần lượt, không chạy đồng thời cả ba; nếu lỗi, đọc nguyên nhân và tiếp tục checkpoint phù hợp thay vì tạo nhiều bản lặp.
3. Nghiệm thu từng bài: có đủ nội dung và mục con phù hợp loại nghiên cứu; Abstract/Conclusion nhất quán; References khớp nguồn thực dùng; chọn ít nhất hai khẳng định để đối chiếu đoạn bằng chứng. Với bài tính toán, số liệu/bảng/hình phải khớp kết quả runner và baseline. Với khảo sát, số liệu phải khớp CSV, nêu rõ dữ liệu mô phỏng và không bịa người tham gia hay phê duyệt đạo đức. Không còn đoạn dang dở, hình/bảng bị nhắc nhưng không tồn tại hoặc kết luận vượt bằng chứng.
4. Chọn một bài tốt nhất làm bài trình diễn chính và hai bài còn lại để chứng minh hai luồng khác. Trạng thái NEEDS_REVIEW không tự động có nghĩa là không có bản thảo; cũng không có nghĩa đã đạt kiểm định. Đọc finding còn lại và nói rõ giới hạn, không sửa trạng thái để che lỗi.
5. Ghi URL từng bài; tải bản xuất thực tế, mở thử file và lưu ảnh màn hình kết quả. Với bài tính toán, giữ cả CSV, metrics, hình và nhật ký; với khảo sát, giữ protocol và thông tin nguồn gốc dữ liệu. Sao lưu database và artifacts bằng quy trình backup của bản release. Không đưa API key vào slide hoặc file chia sẻ.
6. Diễn tập một lượt chỉ mở kết quả đã lưu: đăng nhập → dashboard → bài báo → nguồn/bằng chứng → thí nghiệm hoặc protocol → monitor → xuất file. Mở sẵn tab và file dự phòng trước khi chia sẻ màn hình.

### Khi trình bày: khoảng 10–12 phút

1. **1 phút:** vấn đề, mục tiêu và lý do có ba luồng lấy bằng chứng.
2. **3 phút:** bài tổng quan đã lưu; chỉ ra cấu trúc, một luận điểm, nguồn và đoạn bằng chứng tương ứng.
3. **3 phút:** bài tính toán đã lưu; chỉ ra CSV, baseline, kết quả chương trình đã chạy, hình và thông tin tái lập.
4. **2 phút:** bài khảo sát đã lưu; chỉ ra protocol, dữ liệu mô phỏng, kết quả và lịch sử chờ/tiếp tục nếu có. Không cần chạy lại workflow chỉ để chứng minh bước chờ.
5. **1–3 phút:** monitor/lịch sử xử lý, vai trò các agent, kiến trúc và giới hạn. Có thể mở form tạo bài hoặc duyệt một kế hoạch nếu provider đã kiểm tra còn hoạt động; không lấy việc sinh xong bài mới làm điều kiện hoàn thành phần demo.

**Lời dẫn:** “Đây là các bài em đã chạy trước trên chính hệ thống và kiểm tra để trình bày đầy đủ kết quả trong thời gian demo. Em sẽ cho xem đầu vào, nguồn, nhật ký xử lý và đầu ra đã lưu.”

**Dự phòng:** nếu API lỗi, tiếp tục mở dữ liệu đã lưu; nếu ứng dụng không truy cập được, dùng file đã xuất và ảnh/video diễn tập, nói rõ đó là bản ghi kết quả trước đó. Xem kết quả đã lưu không cần gọi lại LLM, nhưng giao diện vẫn cần ứng dụng và database hoạt động.

**Kiểm tra ngày 10/11:** endpoint readiness báo database/broker sẵn sàng và sáu dịch vụ demo healthy. Database có bản thảo cho cả ba loại; các bản có nội dung hiện vẫn là NEEDS_REVIEW. Đây là kiểm tra khả năng vận hành và sự tồn tại của dữ liệu, chưa phải nghiệm thu chất lượng nội dung hoặc xác nhận ba lượt chạy mới đã thành công. Bản tổng quan mới nhất ghi nhận 3.873 từ và 18 nguồn thu thập; chưa được coi là bản tốt nhất chỉ dựa trên hai con số này.


### Cấu hình API và tối ưu token — 10/11/2026

- Khuyến nghị thử nghiệm trả phí: OpenRouter, base URL `https://openrouter.ai/api/v1`, model cố định `google/gemini-2.5-flash`. Tắt bộ lọc chỉ model miễn phí khi tải danh sách. Giá catalog kiểm tra ngày 10/11: 0,30 USD/triệu input và 2,50 USD/triệu output; nhập/kiểm tra hai mức này trong Settings để ước tính chi phí đúng. Nguồn: https://openrouter.ai/google/gemini-2.5-flash/pricing . Đây là lựa chọn cân bằng chi phí để diễn tập, chưa có lượt chạy trả phí chứng minh tốt hơn các model khác trong dự án.
- Giới hạn mỗi phản hồi: 16.384 token; reasoning low; JSON Schema. Đây là trần khả năng, không phải yêu cầu model phải dùng hết. Mỗi bước JSON ngắn được cấp theo nhu cầu (thường 4.096); Critic tối đa 8.192; mỗi nhóm Writer theo mục tiêu số từ. JSON bị cắt có tối đa một lần thử lại với dung lượng tăng có kiểm soát.
- Form tạo bài: trần ước tính 0,50 USD/bài, 30 phút, 40 lượt gọi, 150.000 input / 60.000 output token; 12 nguồn, STANDARD, MEDIUM. Hạn mức 150.000/60.000 theo giá model trên tương ứng khoảng 0,195 USD tiền model, không phải báo giá hoặc bảo đảm hóa đơn. Ba bài với trần 0,50 USD/bài có tổng trần ước tính 1,50 USD; phí nạp tiền, dịch vụ khác và sai lệch giá khai báo phải được xem riêng. Không tự chạy chiến dịch trả phí khi chưa chốt ngân sách thực hiện.
- Kiểm tra key/model không sinh nội dung. **Thử phản hồi** kiểm tra một schema lồng nhau, tối đa một request và 2.048 output token. Với kết nối trả phí, cần tick cho phép một lượt thử có tính phí; tick được bỏ sau mỗi lượt và khi đổi model/cấu hình. Kết quả OK không bảo đảm toàn bài hoặc tất cả schema đều thành công.
- Tối ưu tập trung vào dữ liệu trung gian: bỏ metadata hiển thị trong schema prompt, JSON gọn, bớt lặp toàn văn những nhóm đã viết. Các nhóm thân bài nhận trích đoạn để nhất quán; nhóm Abstract nhận toàn bộ thân bài đã lưu. Không cắt bài cuối, bỏ citation validator, bỏ nguồn hoặc biến phần chưa làm thành kết quả thành công.
- Lỗi `PROVIDER_REQUEST_INVALID` là provider từ chối tham số/định dạng. Không suy ra 429 chỉ vì một thông báo chung có chữ quota. Luôn ưu tiên mã HTTP/loại lỗi đã xác định; không hiển thị raw provider body hay API key.

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

Đăng nhập → **Settings → API & model → Mặc định cho bài mới** → chọn dịch vụ, nhập key và model → **Lưu mặc định**. Không quay màn hình lúc nhập key. Bài mới tự dùng cấu hình đã lưu. Lưu thành công chưa chứng minh provider còn quota.

Đổi một bài hiện có bằng **API & model** ở đầu workspace → **Bài hiện tại**, khi bài không chạy/không ở hàng đợi. Chọn dịch vụ, nhập key → **Tải danh sách model** → chọn model → **Lưu cho bài này**. Key đã lưu được giữ kín; để trống để giữ lại. Một số dịch vụ không cung cấp danh sách thì dùng **Nhập tên model thủ công**. Tải danh sách chưa chứng minh model còn quota hoặc hỗ trợ mọi dạng đầu ra. Với OpenRouter, bộ lọc miễn phí bật mặc định; dịch vụ khác có chính sách giá riêng.

Kết nối riêng được ưu tiên hơn provider máy chủ. Nếu kết nối riêng lỗi, hệ thống không tự chuyển sang dùng tín dụng máy chủ. Đổi mặc định chỉ áp dụng cho bài mới; bài cũ phải chọn **Dùng cấu hình mặc định** trong **Bài hiện tại**. Đổi model không đặt lại lượng sử dụng. API miễn phí vẫn có giới hạn tốc độ/hạn mức.

**Thao tác khi chạy:** thanh đầu workspace có **Dừng nghiên cứu** khi đang chạy/chờ. Bài lỗi có **Tiếp tục từ bước lỗi / Continue from failed step**: tiếp tục checkpoint, giữ kết quả đã lưu và lượng sử dụng. Nút **Kiểm tra bản thảo đã lưu / Check for saved draft** chỉ tải lại bản thảo, không chạy workflow. Đổi model không đặt lại ngân sách.

**Khi chạm hạn mức:** bài tạm dừng và giữ phần đã làm. Vùng khôi phục hiển thị token, lượt gọi, thời gian và chi phí ước tính đã dùng so với giới hạn của bài. Nếu còn trong trần hệ thống, người dùng duyệt mức tăng được đề xuất rồi tiếp tục cùng checkpoint; lượt dùng cũ không bị xóa. Trần hiện tại trong code là 500.000 input, 200.000 output token, 100 lượt gọi model, 60 phút hoạt động và 2 USD chi phí ước tính. Có thể tăng trần chi phí của bài khi chạm mức tự chọn, nhưng phải duyệt rõ ràng và không vượt 2 USD. Hạn mức của provider miễn phí là giới hạn riêng; tăng hạn mức bài không cấp thêm quota cho provider.

Lỗi và bước lỗi hiện ngay trong khung đỏ. Lỗi 503 là provider quá tải, khác với key bị từ chối (401/403), model không khả dụng (404) và giới hạn dịch vụ (429). Retry tự động cho lỗi 502/503/504 có giới hạn và vẫn chịu ngân sách. Với 429 tạm thời có tín hiệu phù hợp, hệ thống lưu thời điểm thử lại, đưa bài về hàng đợi và giải phóng worker; giao diện báo **Đang chờ dịch vụ AI**. Tối đa hai lần hoãn tự động trong cùng workflow, mỗi lần không quá 300 giây; hết hạn mức ngày hoặc không xác định được thời gian chờ thì cần người dùng xử lý. Nếu Writer đã lưu bản thảo trước khi Critic gặp lỗi provider, bản thảo có thể được giao dưới trạng thái **Cần rà soát**, không được ghi là kiểm tra thành công.

**Chọn model:** danh sách đánh dấu **JSON Schema** khi dịch vụ quảng bá khả năng này. Khi chọn, ứng dụng ưu tiên định dạng đó; schema có trường từ điển động vẫn dùng JSON object và kiểm tra bằng code để giữ đầy đủ dữ liệu. Đây là kiểm tra khả năng kết nối, không bảo đảm model sẽ viết đúng hoặc còn quota. Khi trả JSON lỗi, có tối đa một lượt yêu cầu sửa định dạng, vẫn tính trong ngân sách. Phản hồi bị cắt không được ghép đoán thành kết quả hợp lệ.

**Giữ phần đã làm:** các đầu ra có cấu trúc đã kiểm tra được lưu riêng cho đúng bài, workflow, input và cấu hình model. Tiếp tục cùng điều kiện có thể dùng lại chúng; đổi cấu hình/input không tái dùng kết quả không còn khớp. Với kết nối cá nhân và bài MEDIUM/LONG, Writer viết theo nhóm phần ngay từ đầu để tránh mất một lượt toàn bài do timeout. Các trường hợp khác vẫn có thể chuyển sang nhóm khi timeout/cắt. Giao diện hiển thị số nhóm đã lưu; chỉ lắp bản thảo khi đủ nhóm hợp lệ, không trình bày bài đang viết dở như đã hoàn tất.

Nút **Mục lục / Contents** nằm bên trái tiêu đề và chỉ điều khiển cột trái. **Ẩn tiến trình / Hide pipeline** ở thanh trên điều khiển cột phải; khi thu gọn, nút đổi thành **Mở tiến trình / Show pipeline**, đồng thời có nút **Pipeline** ngay mép phải trên desktop. Hai cột hoạt động độc lập. **Inspect Error** trong Monitor chuyển tới lịch sử lỗi trên chính trang Monitor. Khi bài tính toán chờ dữ liệu, ô chọn CSV xuất hiện ngay trong workspace; upload hợp lệ tự tiếp tục, không cần bấm chạy lại. Bài khảo sát vẫn cần file và thông tin nguồn gốc rồi bấm **Tiếp tục**.

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

Chọn luồng theo **việc cần làm**, không chỉ theo chủ đề. Câu hỏi về spaced practice ở bài A là đọc và tổng hợp nghiên cứu, nên chọn REVIEW. Chỉ chọn tính toán nếu có phép thử được hỗ trợ và dataset phù hợp; chọn nhầm sẽ đưa bài qua bước thiết kế/thực nghiệm không cần thiết. Giới hạn token/lượt gọi vẫn áp dụng kể cả khi chi phí ước tính là 0 USD.

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
| `QUEUED` | Chờ worker; nếu có thông báo chờ dịch vụ AI thì xem thời điểm tự thử lại. Nếu không có và chờ lâu, kiểm worker/dispatcher |
| `RUNNING` | Đang xử lý; xem bước mới nhất trong monitor |
| `WAITING_APPROVAL` | Cần duyệt/sửa kế hoạch |
| `WAITING_USER_DATA` | Cần dataset hoặc dữ liệu khảo sát, upload đúng ô |
| `NEEDS_REVIEW` / `PARTIAL` | Có thể có bản thảo nhưng còn thiếu sót; đọc lý do, không coi là đã đạt |
| `FAILED` | Đọc khung đỏ; sửa nguyên nhân/cấu hình nếu cần rồi bấm **Continue from failed step** |
| 429 | Provider giới hạn tốc độ/hạn mức. Chờ hoặc cấu hình dịch vụ/model còn quota; không retry liên tục |
| Thiếu bằng chứng | Bổ sung nguồn/kết quả, không yêu cầu Writer tự lấp chỗ trống |
| Chạm hạn mức bài | **Xem hạn mức để tiếp tục** → đọc mức đang dùng và mức tăng đề xuất → chủ động duyệt rồi tiếp tục cùng bài nếu còn dưới trần hệ thống. Có thể tăng cả trần chi phí ước tính của bài trong mức 2 USD; quota của provider vẫn là giới hạn riêng. Khi đã chạm trần hệ thống, giữ bài cũ và tạo bài mới với phạm vi phù hợp |

## 6. Hiểu code để trả lời thầy

**Một lần bấm bắt đầu:** Next.js gửi yêu cầu → FastAPI kiểm người dùng và lưu bài → outbox lưu ý định gửi việc → Redis chuyển job → Celery worker chạy LangGraph → agent dùng nguồn/công cụ → PostgreSQL và kho file lưu kết quả → giao diện đọc qua API. Bản hiện tại có polling; không giới thiệu SSE replay là đã nghiệm thu.

| Thành phần | Hiểu đơn giản | Nơi đọc code |
|---|---|---|
| Next.js / React | Giao diện, tạo bài, đọc bài và monitor | `frontend/src/app/`, `frontend/src/lib/api.ts` |
| FastAPI / Pydantic | API, xác thực và kiểm dữ liệu | `backend/app/api/v1/`, `backend/app/schemas/` |
| PostgreSQL / SQLAlchemy | Lưu bài, nguồn, trạng thái và phiên bản | `backend/app/models/`, `backend/alembic/versions/` |
| Redis / Celery | Gửi và chạy việc dài ở nền | `backend/app/services/task_dispatcher.py`, `backend/app/worker.py` |
| LangGraph | Chuyển bước, vòng lặp, dừng và tiếp tục | `backend/app/agents/graph.py`, `state.py`, `nodes.py` |
| Prompt riêng | Nội dung chỉ dẫn ở file txt, code chỉ truyền dữ liệu | `backend/app/prompts/templates/`, hướng dẫn trong `backend/app/prompts/README.md` |
| Runner / intake | Tính baseline/Ridge và kiểm dữ liệu khảo sát | `backend/app/services/experiment_runner.py`, `isolated_experiment.py`, `fieldwork_intake.py` |
| API/model Settings | Lưu khóa mã hóa và cấu hình mặc định/riêng | `backend/app/services/user_model_settings.py`, `model_connection.py` |

**Năm role cốt lõi:** Supervisor lập kế hoạch → Researcher tìm nguồn → Evidence Analyst phân tích → Writer viết → Critic phản biện. Methodologist và nhánh thực nghiệm dùng khi cần. Curator, validators và runner có phần xử lý bằng code; không phải mọi module đều là LLM agent.

Critic có thể yêu cầu Writer sửa hoặc quay lại tìm nguồn. Hai vòng đều có giới hạn. Critic là kiểm tra nội bộ, không phải peer review độc lập.

Kiến trúc là **modular monolith**, API/worker chạy thành các tiến trình riêng; không tách từng agent thành microservice. Pattern chính: graph/state machine, transactional outbox, worker claim chống chạy lặp, dependency injection và provider adapter. Không hứa exactly-once toàn hệ thống hay loại hết hallucination.

Dùng VS Code để đọc/debug code; Antigravity khi muốn AI hỗ trợ sửa. Cùng một thư mục dự án, không cần tạo bản sao. Tránh để hai công cụ cùng sửa một file.

## 7. Trạng thái kiểm chứng — 08/11/2026

Mã nguồn `52beacc` trên branch `feature/89-demo-workflow`, draft PR #109 vào develop: bộ backend đầy đủ tại local **954 test passed** trên database thử nghiệm riêng. Bản giao diện không đổi từ mốc **70 frontend test passed** và production build thành công. CI chạy lại mỗi lần cập nhật PR; kiểm tra các jobs đạt trước khi merge. Không lấy số test này làm bằng chứng rằng mọi bài mới với provider miễn phí đều hoàn tất. Bản demo vẫn dùng **http://127.0.0.1:3082**; chưa merge vào main.

Docker demo đã triển khai revision **`52beacc7bcdb`**; sáu dịch vụ healthy sau migration. Các lượt kiểm tra provider ngày 06/11 dưới đây chạy trên `1c34ad0`, trước bản sửa dừng Analyst sớm ở `49a15a0`.

**Bổ sung 08/11:** Methodologist sinh một bộ trường có cấu trúc; ứng dụng trình bày đề cương từ chính các trường đó. Các nhóm Writer dùng trường tiêu đề/mục con riêng, renderer trình bày H2/H3 để tránh ghép tiêu đề với cả đoạn văn. Contract v7 kế thừa kiểm tra nguồn gốc phương pháp và research gap vượt corpus, đồng thời phát hiện marker nội bộ tự tạo. Những kiểm tra này hỗ trợ phát hiện lỗi, không thay xác minh học thuật. Contract và bản thảo lịch sử không được tự nâng cấp.

**Hai cột độc lập:** nút **Contents / Mục lục** ở bên trái tiêu đề chỉ đóng/mở mục lục. Nút **Hide pipeline / Show pipeline** ở bên phải chỉ đóng/mở tiến trình. Khi đóng từ bên trong Pipeline, cạnh phải vẫn có nút **Pipeline** để mở lại. Đã kiểm tra các thao tác này trên trình duyệt bằng tài khoản QA riêng, không gọi AI cho bài kiểm tra giao diện.

**Hết hạn mức bài:** bấm **Review token allowance / Xem hạn mức để tiếp tục**, đọc mức đã dùng và đề xuất, rồi chọn **Approve limits and continue / Duyệt hạn mức và tiếp tục** nếu nút xuất hiện. Nguồn, dữ liệu, run, checkpoint và lượng đã dùng được giữ nguyên. API có thể đề xuất tăng token, lượt gọi, thời gian hoặc trần chi phí ước tính trong giới hạn hệ thống; không tự tăng khi chưa bấm duyệt. Nếu không có đề xuất, đọc lý do trong vùng khôi phục. Giới hạn provider bên ngoài phải xử lý riêng.

### Kiểm tra tiếp tục và bài mới — 08/11

Hai lượt kiểm tra COMPUTATIONAL dùng CSV giả lập 120 dòng, kết nối cá nhân giới hạn upstream miễn phí, không chuyển sang tiền máy chủ. Không thay mặc định model của người dùng. Sau lỗi router, riêng bài kiểm tra dùng model cố định `nvidia/nemotron-3.5-super-vl:free`, reasoning tắt, output cap 16.384 và JSON Schema; model miễn phí có thể thay đổi khả dụng.

| Lượt kiểm tra | Kết quả thực tế | Giới hạn |
|---|---|---|
| `0f12228d-2d2d-4f8c-bfef-c6050b8460ca` | Nâng hạn mức rồi retry giữ cùng run/thread. Có bản thảo 2.095 từ, 9 mục con, 4 nguồn. | Phát hiện tiêu đề mục con dính đoạn văn và marker metrics/manifest tự tạo. Đây là đầu vào để sửa schema H3 và kiểm tra marker, không phải bản thảo đã nghiệm thu học thuật. |
| http://127.0.0.1:3082/research/de47040a-4a40-4cd3-890e-ee86cbb37825 | Protocol → chờ/upload → chạy routine và kiểm tra lặp lại → lưu 3/4 nhóm → thiếu input token → người kiểm tra tăng hạn mức → tiếp tục cùng run/thread → lưu đủ 4/4 nhóm. Bản thảo 3.399 từ, 19 mục con, 6 nguồn; ledger giữ 20 calls và 17.531 output token. | Vẫn **NEEDS_REVIEW**: research gap chưa rõ; vượt mục tiêu độ dài MEDIUM. Đọc thủ công còn thấy thiếu Table 1 và diễn giải hình hai cột MAE thành lỗi từng quan sát. Không sửa ngược bản lịch sử để che các vấn đề này. |

Từ hai lỗi nội dung trên, rendering policy v2 cho kế hoạch mới bổ sung bảng baseline/Ridge trực tiếp từ metrics của routine đã COMPLETED và kiểm tra tham chiếu bảng/hình. Hình MAE được chú thích rõ là hai giá trị tổng hợp. Đã chạy lại validator trên chính văn bản cũ: phát hiện cả hai vấn đề; dựng bảng từ metrics loại lỗi thiếu bảng, còn diễn giải hình vẫn được giữ thành finding cần sửa. Thao tác kiểm tra này không ghi lại database hay thay phiên bản bài cũ. Đây là sửa hệ thống và regression tests; chưa có chiến dịch mới chứng minh mọi loại bài đều đạt sau thay đổi. Ba luồng demo bên dưới là các bản đã chạy trước, không phải ba lượt mới cùng PASS.

### Cấu hình đầu ra và xóa bài

**Cập nhật cấu hình 09/11:** theo [catalog OpenRouter](https://openrouter.ai/api/v1/models), model miễn phí hỗ trợ output có cấu trúc với mức đầu ra công bố lớn nhất khi kiểm tra là `dots-studio/dots-3-note-preview:free`: 460.800 token, context 512.000. Đây là giới hạn công bố, không phải độ dài bắt buộc hoặc cam kết chất lượng. Một probe JSON nhỏ bằng kết nối đang lưu đã trả đúng, provider ghi nhận 0 USD. Tải danh sách model sẽ dùng mức tối đa được công bố khi chọn model; có nút **Dùng mức tối đa của model** trong tùy chọn.

Giới hạn phản hồi và hạn mức **cả bài** là hai thứ khác nhau: request chỉ dùng tối đa phần output allowance còn lại. Không tự tăng token tổng/tiền/lượt/thời gian hoặc reset usage. Bài cũ giữ snapshot riêng; muốn dùng cấu hình mới, mở **API & model → bài hiện tại → áp dụng mặc định** khi bài đã dừng.

Mức tối đa của model là **trần cấu hình**. Hệ thống cấp dung lượng theo phần việc, thông thường tối đa 16.384 token cho một nhóm Writer/JSON; JSON bị cắt có tối đa một lần thử lại với trần gấp đôi nếu còn ngân sách. Không dành toàn bộ hạn mức bài cho một phản hồi. Một thử nghiệm request quá lớn đã gặp timeout và bị ghi nhận toàn reservation do không có usage; đó là lỗi kiểm tra được giữ lại, không phải bài đã hoàn tất.

`TASK_TIME_LIMIT` nghĩa là hết thời gian hoạt động đã chọn cho bài; có thể duyệt thêm thời gian trong giới hạn 60 phút để tiếp tục cùng checkpoint. Chỉ thêm output token không giải quyết được. API không gửi budget vẫn giữ mặc định lịch sử 900 giây; form tạo bài hiện gửi 30 phút và cho chọn 15–60 phút. `PROVIDER_TIMEOUT` là một lần gọi dịch vụ phản hồi quá lâu và có thể tiếp tục nếu các hạn mức khác còn đủ. `MODEL_INVALID_JSON` nghĩa là kết quả không đúng cấu trúc yêu cầu, chưa đủ để kết luận key sai hay model không hỗ trợ JSON. Không tự động retry vô hạn để che các lỗi này.

**Xóa bài:** mở **Thông tin & Cấu hình / Metadata**, kéo xuống **Vùng nguy hiểm**, chọn **Xóa bài nghiên cứu** và xác nhận. Bài bị ẩn ngay, dữ liệu riêng được đưa vào hàng đợi dọn bền vững; đây là xóa vĩnh viễn, không phải lưu trữ tạm.

### Ba bản thảo có thể mở để demo

Các bản này là **kết quả đã chạy trước**, không giới thiệu như vừa sinh tức thì. Cả ba có đủ phần chính, các mục con, Conclusion và References; không còn marker claim nội bộ chưa được chuyển đổi. Cả ba vẫn là **NEEDS_REVIEW**, không phải bài đã qua peer review hoặc được xác nhận đạt Q1.

| Luồng và đường dẫn mở trực tiếp | Đã kiểm tra thực tế | Giới hạn cần nói rõ |
|---|---|---|
| **A — Tổng quan:** http://127.0.0.1:3082/research/54d2e57e-4732-4743-bba0-fd1b3f99cdd0 | Bản thảo 2.464 từ, 14 mục con, 3 nguồn được dẫn. Có phạm vi tìm kiếm, tổng hợp theo chủ đề, Discussion và Conclusion. | Khôi phục từ Writer sau khi phản biện bị gián đoạn. Còn góp ý về research gap và cách mô tả phương pháp tìm tài liệu. Phạm vi nguồn nhỏ; không gọi là tổng quan hệ thống đầy đủ. |
| **B — Tính toán:** http://127.0.0.1:3082/research/af6b2a7e-609b-4aa2-8a68-90238508045e | Upload 120 dòng CSV; routine và kiểm tra lặp lại hoàn tất. Bản thảo 2.708 từ, 16 mục con, 3 nguồn / 4 citation records; có bảng và hình MAE từ kết quả đã chạy. | Một tập dữ liệu giả lập, một lần chia train/test. Critic đã chạy nhưng ngân sách giới hạn việc kiểm tra; trạng thái bản thảo vẫn cần rà soát. Còn góp ý về research gap, văn phân tích và câu dùng “significantly improves” khi chưa có kiểm định. Không suy ra ưu thế tổng quát hoặc ý nghĩa thống kê. |
| **C — Nghiên cứu ngoài hệ thống:** http://127.0.0.1:3082/research/168039ac-79be-4fe4-94ff-b9463381f664 | Protocol → chờ dữ liệu, giải phóng worker → nhận CSV 24 dòng cùng nguồn gốc → tiếp tục → lưu bản thảo 1.623 từ, 13 mục con, 4 nguồn / 7 citation records. Means, sample SD và tần suất khớp CSV. | Dữ liệu **synthetic**, không phải người tham gia thật. Critic gặp JSON lỗi/timeout; bản thảo được giữ lại với giới hạn phản biện rõ ràng, không ghi PASS. Còn góp ý về research gap. |

Một nguồn có thể hỗ trợ nhiều claim/citation records. Không lấy số citation records làm số bài báo được trích độc lập. Chỉ thêm nguồn liên quan có bằng chứng; không chèn bibliography cho đủ số lượng.

### Kiểm tra xuất bản thảo

Đã gọi API xuất theo đúng phiên bản cho cả A/B/C, với cả hai mẫu **IEEE_CONFERENCE** và **ACM_SIGCONF**: **6/6 thành công**. Đã kiểm tra ZIP hợp lệ, chứa `main.tex`, bản Markdown, provenance và danh mục nguồn; file TeX có các subsection. Bài B có SVG, dữ liệu và phần vẽ hình từ số liệu đã ghi nhận. Đây là **bộ nguồn để định dạng bài**, chưa phải xác nhận đã biên dịch PDF, đáp ứng mọi quy định của hội nghị hoặc được chấp nhận xuất bản.

### Những lỗi luồng đã sửa

| Vấn đề | Hành vi hiện tại |
|---|---|
| Không rõ vì sao bài dừng | Khung đỏ hiển thị nhóm lỗi và bước lỗi; phân biệt xác thực, model, hạn mức, quá tải, timeout, JSON và ngân sách. Không đưa key hay phản hồi thô của provider ra màn hình. |
| Chạy lại làm lại từ đầu hoặc xung đột checkpoint | Retry tiếp tục bước lỗi của workflow hiện tại; giữ kết quả đã lưu, lịch sử và ngân sách. Có kiểm thử nhiều lần lỗi liên tiếp với checkpoint PostgreSQL. |
| Bấm tiếp dù allowance không đủ | API chặn retry vô ích. Người dùng có thể chủ động tăng token, lượt gọi, thời gian hoặc trần chi phí ước tính trong mức tối đa của hệ thống rồi tiếp tục cùng checkpoint; cập nhật hạn mức và outbox nằm trong cùng giao dịch, không reset usage. |
| Không biết đang chờ worker hay dịch vụ AI | Chờ 429 tạm thời có thông báo và thời điểm thử lại; worker được giải phóng. Giới hạn ngày không bị retry vô hạn. |
| Lặp lại đầu ra đã làm khi retry | Tái dùng JSON hợp lệ theo đúng workflow/input/config; Writer dài có thể lưu từng nhóm phần và tiếp tục nhóm còn thiếu. Không dùng output bị cắt như bản hoàn chỉnh. |
| JSON lỗi bị biến thành “không có bằng chứng”, rồi hết budget | Analyst dừng và giữ nguyên lỗi provider. Chỉ extraction hợp lệ rỗng mới có nghĩa là chưa tìm được claim hỗ trợ. |
| Writer xong nhưng Critic lỗi làm mất cả bài | Chỉ giữ bản thảo đã được bước Writer lưu vào checkpoint đúng bài/run/lượt hiện tại. Ghi **Cần rà soát**, phản biện chưa hoàn tất; không coi lỗi workflow bất kỳ là đã tạo bài thành công. |
| Không thấy Dừng / Chạy lại / bật lại sidebar | Các nút nằm trên thanh đầu workspace; Pipeline mở lại cột phải. Inspect Error ở lại trang Monitor, không quay về workspace. |
| Chờ CSV nhưng không thấy chỗ upload | Ô dữ liệu xuất hiện trong workspace. CSV tính toán hợp lệ tự tiếp tục; khảo sát cần thêm thông tin nguồn gốc rồi bấm Tiếp tục. |
| Lưu nhầm cấu hình bài cũ và mặc định | Nút phân biệt **Lưu cho bài này** và **Lưu mặc định**. Đổi mặc định áp dụng cho bài mới; bài cũ dùng thao tác áp dụng mặc định riêng. |
| Tính token bị phình khi đọc JSON | Giữ usage của phản hồi đã hoàn tất, kể cả khi JSON không đạt schema. Thiếu usage hoặc timeout vẫn ghi nhận thận trọng; không reset ledger. Dự trù theo cap thực tế của node, giữ dung lượng người dùng đã chọn; không ép mọi model suy luận vào 4.096 token. |
| Monitor báo dùng Gemini embedding dù chạy key riêng | Kết nối cá nhân dùng lưu văn bản / lexical retrieval, không gọi embedding máy chủ; bản ghi mới thể hiện đúng và không tính phí embedding giả định. |
| Kết luận mạnh hơn số liệu | Kiểm tra bổ sung các cụm như “significantly improves/reduces/increases” khi không có kiểm định đã ghi nhận. Kiểm tra bằng code là bộ lọc hỗ trợ, không bảo đảm mọi lập luận đều đúng. |

### Kết nối miễn phí và các lượt mới

Kết nối mặc định của tài khoản hiện đã lưu là **OpenRouter / openrouter/free**; key được giữ kín. Bài dùng kết nối riêng không tự chuyển sang provider máy chủ hoặc dịch vụ trả phí khi lỗi. Các con số chi phí lịch sử từ cấu hình máy chủ là **ước tính**, không phải bằng chứng người dùng đã bị thu tiền. Không sửa lịch sử chi phí chỉ vì vừa đổi key/model.

Lượt tổng quan `ed03bf8d-2c16-4ca0-9faf-83ac813f97c9` thu được nguồn nhưng trích xuất chỉ xác thực được một nguồn, sau đó Writer timeout; **không có bài mới đủ để nghiệm thu**. Lượt `ab0dd983-ac18-43a5-a25a-bc5aed9f8782` thử model miễn phí cố định; sau timeout, một lần retry với model khác trong catalog nhận **429** ở Supervisor. Không dùng hai lượt này làm ví dụ đầu ra tốt và không tiếp tục retry liên tục.

Bản demo local đã tăng thời gian chờ mỗi provider call lên **180 giây**, vẫn giữ trần thời gian hoạt động mỗi bài và các giới hạn khác. Key hợp lệ hoặc tải được danh sách model không chứng minh model còn quota, hỗ trợ schema ổn định hoặc viết tốt bài dài. Khi 429, chờ theo chính sách dịch vụ hoặc lưu kết nối còn hạn mức trong Settings; không nhập key vào chat. Chỉ thay đổi model sau khi dừng bài nếu bài đang chạy.

**Mức nghiệm thu:** ba luồng có bản thảo thật và bộ nguồn xuất được; các thao tác chính và lỗi đã có kiểm thử. Chất lượng lập luận, độ phủ tài liệu và độ ổn định của provider miễn phí vẫn cần rà soát. Không tuyên bố đã test mọi trường hợp, không còn lỗi, hoặc bài đạt chuẩn xuất bản chỉ dựa vào số test.

### Kiểm tra lại với OpenRouter/free — 06/11, sau bổ sung phục hồi

Chạy **tuần tự**, mỗi bài tối đa 12 LLM calls, 100.000 input token, 50.000 output token, 900 giây hoạt động; model `openrouter/free`, output cap 8.192, reasoning low, ưu tiên JSON Schema khi schema phù hợp. Kết nối giới hạn nhà cung cấp miễn phí và không chuyển sang tín dụng máy chủ. Tổng số call được ghi nhận của ba bài là **24**, dưới trần chiến dịch 36. Đây là kiểm tra smoke có giới hạn, không phải benchmark chứng minh chất lượng giữa các model.

| Bài kiểm tra mới | Kết quả quan sát được | Kết luận |
|---|---|---|
| REVIEW — `1fc22521-50fd-48f7-8e01-451d471a27ec` | Duyệt kế hoạch → tìm nguồn → Analyst gặp JSON lỗi/cắt nhiều lần → `BUDGET_LIMIT`; 6 calls, 43.803 output token được ghi nhận | Chưa có bản thảo. Phát hiện việc Analyst nuốt lỗi rồi làm tiếp; đã sửa dừng sớm và kiểm thử trong `49a15a0`. Không xóa lượng đã dùng của lượt này. |
| COMPUTATIONAL — `284bc5ca-ad57-456b-acb1-0c98b5476124` | Tới Methodologist rồi `MODEL_OUTPUT_TRUNCATED`; 8 calls, 31.930 output token được ghi nhận | Chưa tới upload/chạy routine trong lượt mới; không coi là bài thực nghiệm hoàn tất. |
| HUMAN — `6b81d47c-e89d-4cc3-8f08-7cb765051a1a` | Protocol → `WAITING_USER_DATA` → upload CSV/provenance thành công → Writer timeout → lưu **1/4 nhóm phần** → `BUDGET_LIMIT`; 10 calls, 43.457 output token được ghi nhận | Resume và lưu nhóm đã hoạt động; chưa có bản thảo để phát hành. Nhóm riêng còn có diễn giải quá mức về nguồn gốc thang đo và gap; chưa qua Critic/validation, không dùng làm bài demo hoàn chỉnh. |

Output token ở đây theo ledger: có phản hồi dùng token suy luận và có attempt timeout phải ghi nhận thận trọng khi thiếu usage. Không coi tất cả token là số từ văn bản nhận được hoặc hóa đơn. Cả ba lượt mới **chưa đạt điều kiện bản thảo hoàn chỉnh**; không được thay thế ba bản đã chạy trước bằng các lượt này trong phần trình diễn kết quả. Provider miễn phí và output dài vẫn là hạn chế thực tế; thay đổi phần mềm không thể bảo đảm quota/đầu ra của dịch vụ ngoài.

Bộ fixture đã kiểm offline: routine baseline/Ridge, chạy lại cùng cấu hình và intake khảo sát. Tạo lại bằng môi trường Python dự án, không gọi provider:

~~~powershell
.\.venv\Scripts\python.exe scripts/prepare-demo.py
~~~

Sau buổi trình bày, dừng dịch vụ và giữ dữ liệu:

~~~powershell
.\scripts\release.ps1 -Action stop
~~~

Không chạy `down -v`, không xóa volume và không thay APP_SECRET_KEY của môi trường đang giữ API key mã hóa.
