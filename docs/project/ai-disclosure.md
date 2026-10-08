# Khai báo sử dụng trí tuệ nhân tạo (AI Disclosure)

**Cập nhật hồ sơ:** 08/10/2026. Ghi nhận theo thông tin chủ dự án và lịch sử task; thành viên cần xác nhận trước khi nộp. Không suy đoán model/version hoặc đóng góp từ văn phong.

## 1. Con người chịu trách nhiệm

| Thành viên | Vai trò/đầu ra của con người | Trạng thái hồ sơ |
|---|---|---|
| **Nguyễn Đình Chiến** | Nhóm trưởng; lên kế hoạch, chốt scope/architecture, viết và tích hợp code, kiểm tra runtime, review nội dung AI hỗ trợ, tổng hợp báo cáo | Chủ dự án chịu trách nhiệm toàn bộ phần code/kế hoạch, có AI hỗ trợ; không đồng nghĩa tự viết mọi dòng code. Patch/run evidence ghi theo commit |
| **Phạm Long Vũ** | Chuẩn bị query set, nguồn và rubric; manual QA khi có demo | Phân công; chưa ghi nhận bàn giao trong docs |
| **Nguyễn Văn Hiếu** | User scenarios, progress flow, demo checklist/issue log | Phân công; chưa ghi nhận bàn giao trong docs |
| **Nguyễn Thị Hải My** | Related-work/source matrix, consistency review, biên tập tài liệu | Phân công; chưa ghi nhận bàn giao trong docs |

Phân công không đồng nghĩa đã hoàn thành. Mỗi người xác nhận việc thực tế và AI có hỗ trợ phần đó không.

## 2. AI hỗ trợ quá trình làm dự án

| Công cụ | Việc được ghi nhận | Cách con người kiểm tra | Cần xác nhận |
|---|---|---|---|
| **Google Gemini** | Chủ dự án nói Gemini tạo bản nháp planning docs; các bản được rà soát/chỉnh sửa sau đó | So sánh với yêu cầu, source code và baseline; kiểm tra thuật ngữ/consistency | Model/version, prompt, file/phần giữ/sửa/bỏ |
| **OpenAI Codex** | Rà repository/tài liệu; hỗ trợ baseline; task history ghi patch SQLAlchemy async dependency và State keys; cập nhật SRS/README/docs; các lượt trước hỗ trợ model/migration/registration; ngày 08/10 rà source/kiến trúc, chốt SRS v4.0, ADR-004, diagrams, kế hoạch triển khai/đánh giá | Baseline command/output ghi trong biên bản 27/09; lượt docs có rà link/nội dung tĩnh; lượt planning 08/10 không sửa runtime code hay chạy provider; kiểm tra tài liệu riêng, không thay runtime evidence | Model/version theo app history; patch nào được nhóm chấp nhận; reviewer |
| **Antigravity** | Chủ dự án dự định dùng cho coding và Codex review theo workflow luân phiên; chưa có evidence đủ để liệt kê task cụ thể tại đây | Chỉ thêm task/branch/PR/commit và kết quả review đã xác nhận | Model/version; file đã đổi; ai xác minh |
| **Khác** | Chưa có thông tin xác nhận | — | Thành viên bổ sung khi cần |

Không nêu model/version nếu chưa kiểm tra. Không mô tả AI như reviewer độc lập bảo đảm chất lượng.

## 3. AI bên trong sản phẩm ATI

ATI dự kiến dùng LLM cho plan, synthesis, evidence analysis, writing/critique. Đây khác với AI hỗ trợ nhóm phát triển. Baseline 27/09 chỉ xác minh hạ tầng/task API/graph compile và routing mẫu; chưa có research E2E nên chưa có output sản phẩm được đánh giá để khai báo như kết quả.

## 4. Nguyên tắc báo cáo

1. Nêu model/version chỉ khi có log/lịch sử đáng tin.
2. Ghi tác vụ AI thực sự hỗ trợ; không dùng tỷ lệ phần trăm đóng góp nếu không có phương pháp đo.
3. Con người kiểm tra nguồn, code, test, bảo mật, dữ liệu và nội dung cuối; nhóm chịu trách nhiệm cuối.
4. Không ghi output/patch AI đã được chấp nhận trước khi thành viên xác nhận.
5. Trước khi nộp, điền reviewer cuối, ngày, policy môn học, model/tool xác nhận và task thật đã hoàn thành.
