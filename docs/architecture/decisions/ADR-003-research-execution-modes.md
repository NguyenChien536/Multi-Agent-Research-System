# ADR-003: Hỗ trợ đa phương pháp với ranh giới thực nghiệm có người giám sát

**Trạng thái:** Đã chấp thuận về nguyên tắc sản phẩm; công nghệ isolated runner cần quyết định riêng<br>
**Ngày:** 2026-10-06

## Bối cảnh

Định hướng của giảng viên yêu cầu ATI không chỉ tổng hợp tài liệu mà còn hỗ trợ hypothesis, protocol, thí nghiệm và đầu ra bài báo. Một số nghiên cứu cần code/dataset; loại khác cần phòng lab, khảo sát, thực địa hoặc người tham gia. Chạy code LLM sinh tùy ý trong Celery worker tạo rủi ro RCE; giữ worker sống nhiều ngày để chờ kết quả ngoài đời không phù hợp. Hệ thống cũng không được tạo Results chưa có dữ liệu hoặc tự tiến hành research involving human participants.

## Quyết định

1. ATI là research orchestrator có người giám sát, hỗ trợ study types theo năng lực thực sự được cấu hình; không hứa thực thi mọi phương pháp.
2. Computational path chỉ nhận data schema/type/size hợp lệ và routine được hỗ trợ, có method/config được user xem hoặc duyệt. Chạy qua isolated analysis boundary, không trong API/Celery, giới hạn CPU/RAM/time/filesystem, outbound network mặc định bị chặn. Không chạy arbitrary LLM-generated code.
3. Trước khi chọn sandbox provider/build, cần ADR kỹ thuật riêng và threat model. Nếu chưa đạt safety/feasibility gate, chỉ sinh protocol hoặc dùng result/data do researcher tạo; không giả lập hệ thống đã chạy experiment.
4. Lab/survey/field/human-participant path chỉ sinh protocol/checklist/form draft và ethics notice. Người dùng xin approval và thực hiện bên ngoài. ATI không tuyển người/khởi động nghiên cứu.
5. Hệ thống lưu WAITING_USER_DATA và graph checkpoint, kết thúc worker job. Khi user upload kết quả được phép, API xác minh quyền/file/state, lưu metadata và enqueue resume job idempotent.
6. Article output theo study type. Empirical Results chỉ từ actual data hoặc researcher-provided result có provenance; thiếu data thì output review/protocol/partial draft với phần thiếu được đánh dấu.
7. Macro research loop tối đa 3 lần, dừng sớm nếu không có nguồn/evidence mới sau dedup. Writer/Critic revision cũng giới hạn; budget guard trước mỗi provider call.
8. Monitoring ghi task/agent stage, state, duration, retries, provider usage/cost, artifact lineage và error redacted. Critic không được giới thiệu là peer review độc lập.

## Hệ quả

**Tích cực:** không bó hẹp vào code/AI research; giữ lựa chọn human-led methods; làm rõ provenance/kết quả thật; checkpoint cho thời gian dài; giảm rủi ro mã/dữ liệu không tin cậy.

**Đánh đổi/rủi ro:** study types cần template/method/evaluation domain-specific; runner an toàn tăng effort; researcher chịu trách nhiệm ethics và quyền xử lý data; monitoring cần storage/chi phí và log redaction.

## Release constraint

Đến 10/11/2026 ưu tiên một literature review workflow E2E; tối đa một routine phân tích hẹp nếu safety gate đạt. Human study là protocol + wait/upload/resume target; chỉ báo cáo là implemented sau runtime evidence. ADR không phải bằng chứng tính năng đã xong.

## Tài liệu liên quan

- [System Design](../system-design.md)
- [SRS rút gọn](../../requirements/SRS.md)
- [Roadmap](../../project/roadmap-and-progress.md)
- [Agent Workflow](../../technical/agent-workflow.md)
