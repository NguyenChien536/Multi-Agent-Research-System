# Quy trình phát triển một người

Chiến là người triển khai và quyết định cuối cùng. Quy trình này giữ thay đổi dễ kiểm tra, không tạo thêm người duyệt giả hoặc bắt buộc nhiều nhánh đang chạy cùng lúc.

## Nhánh và đường đi

| Nhánh | Vai trò | Quy tắc |
|---|---|---|
| `main` | Mốc demo/phát hành đã chọn | Chỉ nhận PR từ `develop` hoặc hotfix đã kiểm; tag `vX.Y.Z` tại commit trên `main` |
| `develop` | Nhánh tích hợp | Nhận PR của từng chức năng; có thể chứa việc chưa nghiệm thu runtime nhưng phải ghi rõ |
| `codex/feat-*`, `codex/fix-*`, `codex/chore-*` | Một lát cắt công việc | Tạo từ `develop`, PR về `develop`, xóa sau khi merge |
| `codex/hotfix-*` | Lỗi khẩn cấp trên bản phát hành | Tạo từ `main`, PR về `main`, sau đó đưa cùng sửa đổi về `develop` |

`develop` được khởi tạo ngày 09/10 từ commit auth/ownership `5119866`, **chưa phải bằng chứng chức năng đó chạy thật**. `main` giữ nguyên cho đến khi có nghiệm thu phù hợp.

## Làm một chức năng hoặc sửa một lỗi

1. Chọn một việc từ [Implementation Plan](docs/project/implementation-plan.md), ghi rõ kết quả và gate cần đạt. Giữ tối đa một nhánh feature đang code để giảm đổi ngữ cảnh.
2. `git switch develop`, `git pull --ff-only origin develop`, rồi `git switch -c codex/feat-ten-ngan` (đổi `feat` thành `fix` hoặc `chore` khi phù hợp).
3. Sửa mã và tài liệu liên quan; commit theo dạng `feat(scope): mô tả`, `fix(scope): mô tả` hoặc `chore(scope): mô tả`.
4. Tự đọc diff, ghi chính xác lệnh và kết quả đã chạy. Phân biệt **source đã có**, **kiểm cục bộ đạt**, **runtime/provider thật đã xác minh**. Một build đạt không chứng minh workflow nghiên cứu chạy đúng.
5. Push nhánh và mở PR vào `develop`, điền [mẫu PR](.github/pull_request_template.md). Xem CI và review diff, sửa các lỗi thực tế trước khi merge.
6. Khi gate của một mốc đã đạt, mở PR `develop` → `main`. Tag phiên bản trên commit `main`; Action phát hành đóng gói backend image lên GHCR. Chưa có môi trường đích nên không tự triển khai frontend/backend lên server.

## Các cổng tự động

- [CI](.github/workflows/ci.yml) chạy trên PR và push của `develop`/`main`: biên dịch cú pháp Python và build/typecheck Next.js. CI hiện chưa thay thế kiểm tra DB, Celery, provider hoặc bài báo đầu ra.
- [Release backend](.github/workflows/release-backend.yml) chạy khi push tag `v*` trỏ tới lịch sử `main`; image chạy không có `--reload` và cần cấu hình môi trường/secret khi triển khai.
- `backend/requirements.txt` chưa có lockfile/pin đầy đủ, nên image được tag theo source nhưng rebuild sau này chưa bảo đảm ra cùng dependency. Cần khóa phiên bản trước khi gọi đây là artifact production có thể tái lập.
- Trên GitHub, nên bảo vệ `main` và `develop`: yêu cầu PR, hai check `Backend syntax` và `Frontend build`, chặn force push/xóa nhánh. Với một người code, không đặt yêu cầu một người khác phê duyệt PR nếu không có reviewer thật.

Repo [ATI_Project](https://github.com/VinhDat267/ATI_Project) gợi ý cách dùng nhánh feature, PR template, CI và phân biệt bằng chứng chạy cục bộ với chạy dịch vụ thật. Quy trình này rút gọn cho một người; không sao chép module ownership của nhóm nhiều lập trình viên.
