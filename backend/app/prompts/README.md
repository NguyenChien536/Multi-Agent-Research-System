# Prompt assets

Các chỉ dẫn dài cho model được lưu thành văn bản UTF-8 trong `templates/`, thay vì viết trực tiếp trong Python. Mỗi vai trò có file riêng để dễ đọc, sửa và review trong Git. Không lưu API key, dữ liệu người dùng hay câu trả lời mẫu riêng tư trong các file này.

| File | Dùng cho |
|---|---|
| supervisor.txt | Lập kế hoạch, truy vấn và nhu cầu bằng chứng |
| source_triage.txt | Đánh giá metadata ứng viên nguồn trong bước Researcher |
| evidence_analyst.txt | Trích claim/quote từ đoạn nguồn |
| methodologist.txt | Đề xuất protocol trong phạm vi hệ thống hỗ trợ |
| writer.txt | Viết bản thảo theo loại bài và bằng chứng đã có |
| critic.txt | Phản biện nội bộ về lập luận và chất lượng bài |
| critic_evidence_support.txt | Kiểm hỗ trợ ở cấp statement và dữ kiện thực chạy |
| report_question_answering.txt | Hỏi đáp theo nguồn của phiên bản bài đã lưu |
| structured_output.txt | Chỉ dẫn JSON theo schema cho adapter tương thích |

Ví dụ placeholder: `{{ research_question }}`. Python gọi `render_prompt('writer', research_question=..., ...)`. Chỉ thay văn bản chỉ dẫn; giữ nguyên tên placeholder, không thêm biểu thức Python/Jinja. Loader không dùng eval, không thực thi nội dung và chỉ thay biến một lượt. Nội dung nguồn chứa dấu template vẫn được coi là dữ liệu. Thiếu biến, thừa biến, file trống hoặc template lỗi sẽ bị từ chối.

Code vẫn chịu trách nhiệm về routing, gọi tool, budget, ownership, schema output và kiểm chứng bằng chứng. Cấu trúc loại bài/quy tắc validation có logic vẫn nằm ở service tương ứng; không chuyển chúng thành lời nhắc để model tự quyết định.

Lần tách đầu giữ nguyên nội dung, khoảng trắng và role message hiện có: các node agent vẫn gửi instruction/context theo cách cũ; Q&A và adapter JSON giữ SystemMessage. Đây là tách nội dung khỏi code, không đồng thời thay đổi chiến lược prompting hay chất lượng khoa học đã được nghiệm thu.

Một số dòng đệm cuối file được giữ có chủ ý để đầu vào model giống bản trước; không tự format/trim các template này. Git attributes giữ LF cho các asset và tách quy tắc khoảng trắng của nội dung prompt khỏi lint mã nguồn.

Dev mount thư mục app nên có thể sửa file txt; sau khi code loader đã được nạp, lần gọi tiếp theo đọc nội dung mới mà không cache. Không sửa prompt giữa một bài đang chạy nếu cần tái lập; ghi lại commit sử dụng. Demo/prod đọc assets nằm trong image đã chốt; sửa file trên máy chỉ tác động dev. Muốn đưa prompt mới sang demo phải test, commit và release deploy. Không có endpoint cho người dùng công khai sửa các prompt hệ thống.
