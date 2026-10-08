# Hướng dẫn dự án và phân công cho thành viên

**Dự án:** ATI — Multi-Agent Research System<br>
**Kỳ hạn:** 10/09/2026–10/11/2026<br>
**Thành viên:** Nguyễn Đình Chiến, Phạm Long Vũ, Nguyễn Văn Hiếu, Nguyễn Thị Hải My

Tài liệu giải thích dự án bằng ngôn ngữ không yêu cầu kiến thức lập trình và giao đầu việc rõ. Vũ, Hiếu, My không cần code, cấu hình backend, thiết kế database hoặc review code.

## 1. ATI làm gì?

Người nghiên cứu phải tìm/đọc nguồn, ghi bằng chứng, nêu vấn đề/câu hỏi tiếp theo, chọn phương pháp và trình bày kết quả. AI có thể giúp nhanh nhưng dễ viết quá chắc, trích sai nguồn hoặc tạo kết quả chưa từng đo.

ATI hướng tới điều phối quy trình:

1. Người dùng nhập câu hỏi/chọn loại nghiên cứu, có thể tải paper hoặc dữ liệu của mình.
2. Hệ thống lập kế hoạch, tìm/đọc nguồn và nối nhận định với evidence.
3. Hệ thống gợi ý câu hỏi và khoảng trống nghiên cứu theo phạm vi nguồn đã xem, không tuyên bố chắc chắn là gap của cả lĩnh vực.
4. Đề xuất hypothesis/method/protocol; người dùng xem lại khi cần.
5. Với dataset và phân tích được hỗ trợ, hệ thống chạy routine có giới hạn và lưu output thật. Với lab/khảo sát/thực địa/người tham gia, người nghiên cứu tự xin review cần thiết, tự làm ngoài ATI rồi tải kết quả được phép xử lý.
6. Writer tạo bài/đầu ra đúng loại; Critic rà lỗi có giới hạn; hệ thống cho người dùng xem nguồn, kết quả, cảnh báo và tiến độ.

ATI không tuyển người, không chạy lab ngoài đời và không tự tạo số liệu. Critic không thay giáo viên/peer review. Thiếu data thì báo cáo phải ghi rõ; không giả làm empirical paper hoàn tất.

## 2. Phần nào là demo, phần nào là hướng sau?

**Mục tiêu đến 10/11:** review từ web + PDF có evidence/citation và gợi ý khoảng trống; một experiment CSV chạy thật tạo bảng/biểu đồ và bài thực nghiệm; protocol có chờ/upload/resume; Q&A/sửa bài và tiến độ/log. Phân tích chỉ nhận routine/dataset được hỗ trợ. Với nghiên cứu cần người tham gia/lab, con người thực hiện bên ngoài rồi nạp dữ liệu phù hợp. Experiment là gate bắt buộc; nếu chưa đạt phải ghi rõ, không thay bằng số liệu giả.

Các loại nghiên cứu khác, mọi journal template, PDF polished, ảnh, cộng tác nhóm và production deployment là hướng mở rộng. Không quảng bá là đã xong nếu chưa có demo/test evidence.

## 3. Ai làm gì và vì sao?

| Thành viên | Công việc | Sản phẩm | Ảnh hưởng tới dự án |
|---|---|---|---|
| **Phạm Long Vũ** | Evaluation set và manual QA | 12 câu hỏi (4 pilot, 8 held-out), nguồn và rubric; CSV numeric + dictionary + expected checks; chấm ẩn nhãn và manual QA | Có bộ tình huống thật để kiểm tra report/citation có đúng phạm vi và evidence hỗ trợ claim không |
| **Nguyễn Văn Hiếu** | User scenarios, trạng thái/điểm chờ, demo | 4 scenario, flow đơn giản, checklist, issue log có bước tái hiện | Giúp Chiến ưu tiên UI/API và phát hiện user không hiểu tiến độ hoặc lúc nào cần upload/duyệt |
| **Nguyễn Thị Hải My** | Research background, nguồn, biên tập | Bảng 8–12 nguồn, related-work summary, inconsistency/unsupported-claim review, rà thuật ngữ | Củng cố problem/objectives bằng nguồn thật; ngăn mô tả quá mức hoặc lệch trạng thái |
| **Nguyễn Đình Chiến** | Trưởng nhóm, kế hoạch, kiến trúc, code, tích hợp, xác minh | Code/demo, technical decisions, runtime evidence, review nội dung kỹ thuật, tiến độ/risk | Chuyển đầu ra nghiên cứu/UX/evaluation thành hệ thống và bằng chứng |

Ba thành viên ngoài Chiến không nhận task coding, backend config, database hoặc code review. Mỗi người chịu trách nhiệm deliverable riêng; Chiến xác nhận nội dung kỹ thuật.

## 4. Task của Phạm Long Vũ — Evaluation set

**Task 1 — Chọn câu hỏi (09/10):** tạo 12 câu hỏi nghiên cứu có phạm vi rõ, chia 2–3 chủ đề. Tách 4 câu pilot để chỉnh hệ thống và 8 câu held-out để đánh giá cuối; không dùng 8 câu cuối để tuning prompt. Ghi câu hỏi, đối tượng/thời gian/địa lý và loại output.

**Task 2 — Gắn nguồn và expected points (12/10):** mỗi câu có ít nhất 2 nguồn đáng tin (paper, website chính thức, cơ quan chính phủ, báo cáo có tác giả/ngày). Mở URL, xác nhận đúng nội dung. Ghi 2–4 ý hợp lý và một giới hạn/tranh luận nếu có.

**Task 3 — Tạo rubric (17/10):** theo Evaluation Plan: semantic support dùng nhãn supported/partial/unsupported/contradicted/unverifiable; scope/giới hạn chấm 0–2; citation link đúng/sai ghi riêng. Ghi ví dụ cho từng nhãn và cách xử lý bất đồng trước khi chấm held-out.

**Task 4 — Dataset nhỏ (16/10):** chọn CSV công khai không định danh, các cột số và một target số phù hợp dự đoán. Ghi URL/quyền sử dụng, ý nghĩa cột/đơn vị, số hàng, dữ liệu thiếu và các kiểm tra hợp lý bằng đọc bảng; không tạo số liệu giả. Gửi Chiến duyệt độ phù hợp routine trước 16/10. Không viết code hoặc tự tính kết quả thực nghiệm thay hệ thống.

**Task 5 — Chấm nội dung và QA (03–07/11):** chấm report ẩn tên cấu hình cùng My theo [Evaluation Plan](evaluation-plan.md); hai người chấm đôi ít nhất 20% mẫu, lưu cả bất đồng. Ngày 06/11 chạy checklist của Hiếu trên demo; ghi trang/bước, thao tác, expected/actual result, mức độ, ảnh nếu có.

## 5. Task của Nguyễn Văn Hiếu — User scenarios và demo

**Task 1 — Bốn kịch bản (12/10):**

1. Student làm literature review và upload PDF.
2. User xem plan/gợi ý câu hỏi, yêu cầu sửa rồi hỏi tiếp trên bài; bản sửa phải giữ phiên bản cũ.
3. Nghiên cứu lab/survey: nhận protocol, thấy ethics notice, làm bên ngoài, quay lại upload kết quả.
4. User upload dataset cho routine hỗ trợ, xem bảng/biểu đồ và provenance.

Mỗi kịch bản ghi mục tiêu, input, các bước, trạng thái mong đợi, output, điểm gây bối rối. Nếu chưa có trong demo, ghi rõ “target/chưa có”.

**Task 2 — Flow/wireframe (17/10):** vẽ 5–7 bước bằng giấy/PowerPoint/Figma: input, progress, evidence, report, các trạng thái WAITING_APPROVAL/WAITING_USER_DATA/COMPLETED/PARTIAL/FAILED.

**Task 3 — Demo checklist (25/10):** từng thao tác và kết quả mong đợi: mở demo, tạo task, theo dõi, đọc report, kiểm citation, thử trạng thái chờ nếu có. Thêm các ca kiểm quyền tài khoản khác, hết budget, sửa giữ bản cũ, xóa task và không mở lại qua link cũ; ghi Planned nếu chưa có implementation. Không thêm bước chưa triển khai vào live demo.

**Task 4 — Dry run/issue log (06/11):** chạy checklist với Chiến/Vũ; ghi lỗi theo bước và wording/UI đề xuất; báo ngay lỗi chặn demo.

## 6. Task của Nguyễn Thị Hải My — Research background và biên tập

**Task 1 — Nguồn (bản đầu 12/10, chốt 17/10):** tìm 8–12 nguồn về AI-assisted/deep research, RAG/citation grounding, research workflows/ethics hoặc reporting. Ưu tiên paper/standard/trang chính thức. Ghi tác giả, năm, DOI/URL, loại, phần đã đọc, kết luận, giới hạn và liên quan ATI.

**Task 2 — Cấu trúc bài và related work (18–24/10):** ngày 18/10 bàn giao checklist các mục cần có của REVIEW, EMPIRICAL và PROTOCOL; phân biệt mục kết quả thật với kế hoạch dự kiến. Ngày 24/10 so sánh 3–5 paper/systems theo user, input source, grounding/evaluation, human control, output, bài học và hạn chế. Không kết luận ATI tốt hơn khi chưa benchmark.

**Task 3 — Consistency review (31/10):** rà SRS, system design, roadmap và midterm; ghi mệnh đề thiếu nguồn, claim quá mạnh, diagram/status lệch. Phân biệt target với verified và gợi ý khoảng trống trong nguồn đã xem với khẳng định tính mới toàn ngành.

**Task 4 — Chấm và biên tập (05–07/11):** cùng Vũ chấm ẩn nhãn theo rubric, không sửa điểm để làm hệ thống có vẻ tốt hơn. Ngày 07/11 rà tiếng Việt, thuật ngữ, references, tên thành viên, caption/đánh số hình. Hỏi Chiến khi gặp mệnh đề kỹ thuật.

## 7. Task của Nguyễn Đình Chiến — Technical lead

- Chốt scope/Definition of Done; review kỹ thuật các đầu ra.
- Tự code/auth/migration/upload/workflow/analysis/monitoring; không giao code cho ba thành viên.
- Chọn một demo question từ evaluation set.
- Không chạy workflow có phí nếu chưa có provider/cost cap; không nhận data nhạy cảm nếu chưa có policy.
- Trước khi ghi Verified, lưu ngày, command/test output hoặc ảnh demo và người chạy.

## 8. Mẫu bàn giao và cách phối hợp

Mỗi bàn giao cần có: tên đầu ra, người phụ trách, ngày, link/file, việc đã làm, cách tự kiểm, nguồn (nếu có), điểm chưa chắc chắn/blocker, reviewer và AI có hỗ trợ hay không.

Checklist đánh giá dùng mã G0–G7 ở SRS: Vũ phụ trách nội dung/dataset liên quan G2/G5/G7; Hiếu phụ trách thao tác/trạng thái/quyền liên quan G1/G3/G4/G6; My phụ trách nguồn/cấu trúc bài và chấm nội dung G2/G4/G5/G7. Đây là phân công đánh giá thủ công; Chiến chịu trách nhiệm checks kỹ thuật và xác nhận gate cuối. Ba bạn không cần tự chạy migration, viết test hoặc review code.

Mỗi tuần cập nhật Done / In progress / Waiting review / Blocked kèm link. Nếu trễ quá 2 ngày, báo sớm và giảm scope trước khi dồn việc sang Chiến. Không dùng AI tạo nguồn/số liệu giả hoặc ghi task chưa làm.

### Tin nhắn gửi nhóm

> Nhóm mình làm ATI: công cụ AI hỗ trợ quy trình nghiên cứu có nguồn và có người giám sát. Demo trước 10/11 có tổng quan từ web + PDF, một experiment CSV chạy thật, protocol/chờ data, hỏi đáp/sửa bài và tiến độ. Mọi kết luận phải truy lại được evidence hoặc kết quả thật. Với lab/khảo sát/người tham gia, ATI chỉ tạo protocol; người nghiên cứu xin review và tự làm bên ngoài.
>
> - Vũ: 12 câu hỏi có nguồn + rubric; CSV numeric/dictionary trước 16/10; chấm nội dung và QA thủ công.
> - Hiếu: 4 user scenarios, flow đơn giản, checklist và issue log.
> - My: 8–12 nguồn nền/related work, consistency review, biên tập báo cáo.
> - Chiến: toàn bộ code/technical decisions/integration.
>
> Các bạn không cần code. Mỗi task cần file/link, ngày, cách tự kiểm và nguồn. Hãy báo sớm nếu deadline hoặc scope chưa rõ.

## 9. Liên kết

Kế hoạch kỹ thuật là [implementation-plan.md](implementation-plan.md), cách đánh giá là [evaluation-plan.md](evaluation-plan.md). Nguồn tiến độ là [roadmap-and-progress.md](roadmap-and-progress.md); target diagram là [system-design.md](../architecture/system-design.md); yêu cầu là [SRS.md](../requirements/SRS.md).
