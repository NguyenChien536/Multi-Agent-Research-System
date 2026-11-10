# Synthia frontend

Next.js/React/TypeScript cho Settings, dashboard, workspace, monitor, hỏi đáp và chỉnh sửa bài.

Chạy ứng dụng local bằng Docker theo README ở thư mục gốc; frontend gọi /api/v1 qua gateway cùng origin. API key lưu mã hóa ở backend, không lưu trong browser storage.

Kiểm tra tại thư mục này: `npm ci`, `npm test`, `npm run build`.

Luồng bắt đầu: Settings → lưu API/model → tạo bài → monitor → kiểm nguồn và bản thảo → xuất. Trong workspace, Settings có cấu hình riêng cho bài hiện tại.
