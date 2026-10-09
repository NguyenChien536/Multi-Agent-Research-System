# Quy trình phát triển một người

Chiến là người triển khai và quyết định cuối cùng. Quy trình này giữ thay đổi dễ kiểm tra, không tạo thêm người duyệt giả hoặc bắt buộc nhiều nhánh đang chạy cùng lúc.

## Nhánh và đường đi

| Nhánh | Vai trò | Quy tắc |
|---|---|---|
| `main` | Mốc demo/phát hành đã kiểm | Chỉ nhận PR từ `develop` hoặc `hotfix/*` sau khi toàn bộ check bắt buộc đạt; tag `vX.Y.Z` tại commit trên `main` |
| `develop` | Nhánh tích hợp | Nhận PR của từng lát cắt và chạy đủ CI; chưa tự động được coi là bản phát hành |
| `feature/<issue>-<slug>` | Chức năng mới | Tạo từ `develop`, ví dụ `feature/3-pdf-upload` |
| `bugfix/<issue>-<slug>` | Sửa lỗi | Tạo từ `develop`, ví dụ `bugfix/8-report-access` |
| `chore/<slug>`, `docs/<slug>` | Hạ tầng hoặc tài liệu | Tạo từ `develop`, ví dụ `chore/ci-release-gates` |
| `hotfix/<issue>-<slug>` | Lỗi khẩn cấp của bản đã phát hành | Tạo từ `main`, PR về `main`, sau đó đưa cùng sửa đổi về `develop` |

Slug chỉ dùng chữ thường ASCII, số và dấu `-`; ngắn, mô tả **chức năng/lỗi/kết quả**. Không dùng tên người, tên AI, IDE hay công cụ trong tên nhánh. CI kiểm cấu trúc và một số tên công cụ phổ biến; người mở PR vẫn phải rà tên nhánh theo quy tắc này.

`develop` được khởi tạo ngày 09/10 từ commit auth/ownership `5119866`, **chưa phải bằng chứng chức năng đó chạy thật**. `main` giữ nguyên cho đến khi có nghiệm thu phù hợp.

## Làm một chức năng hoặc sửa một lỗi

1. Chọn một việc từ [Implementation Plan](docs/project/implementation-plan.md), ghi rõ kết quả và gate cần đạt. Giữ tối đa một nhánh feature đang code để giảm đổi ngữ cảnh.
2. `git switch develop`, `git pull --ff-only origin develop`, rồi `git switch -c feature/3-pdf-upload` với mã issue và slug của công việc thực tế; dùng `bugfix/`, `chore/` hoặc `docs/` theo bảng trên.
3. Sửa mã và tài liệu liên quan; commit theo dạng `feat(scope): mô tả`, `fix(scope): mô tả` hoặc `chore(scope): mô tả`.
4. Tự đọc diff, ghi chính xác lệnh và kết quả đã chạy. Phân biệt **source đã có**, **kiểm cục bộ đạt**, **runtime/provider thật đã xác minh**. Một build đạt không chứng minh workflow nghiên cứu chạy đúng.
5. Push nhánh và mở PR vào `develop`, điền [mẫu PR](.github/pull_request_template.md). Xem CI và review diff, sửa các lỗi thực tế trước khi merge.
6. Chỉ mở PR `develop` → `main` sau khi **toàn bộ test hiện có và các check bắt buộc đều pass** trên đúng revision, không có check đang chạy hoặc lỗi bị bỏ qua. Ghi thêm bằng chứng chạy thực tế cho luồng bị ảnh hưởng (DB, worker, provider, UI) theo gate của mốc. Không có bằng chứng thì giữ ở `develop`. Sau merge, tag phiên bản trên commit `main`; Action phát hành đóng gói backend image lên GHCR. Chưa có môi trường đích nên không tự triển khai frontend/backend lên server.

## Các cổng tự động

- [CI](.github/workflows/ci.yml) chạy trên PR và push của `develop`/`main`: kiểm tên/đường đi nhánh, biên dịch cú pháp Python, migrate PostgreSQL+pgvector sạch và chạy **toàn bộ `backend/tests`**, build/typecheck Next.js. Bài test dùng DB riêng và fake dispatch; CI chưa chứng minh Celery/provider hoặc bài báo đầu ra chạy thật.
- [Release backend](.github/workflows/release-backend.yml) chạy khi push tag `v*` trỏ tới lịch sử `main`; image chạy không có `--reload` và cần cấu hình môi trường/secret khi triển khai.
- `backend/requirements.txt` chưa có lockfile/pin đầy đủ, nên image được tag theo source nhưng rebuild sau này chưa bảo đảm ra cùng dependency. Cần khóa phiên bản trước khi gọi đây là artifact production có thể tái lập.
- Bảo vệ `main` và `develop` yêu cầu PR, nhánh cập nhật với base, lịch sử tuyến tính, chặn force push/xóa nhánh và áp dụng cả chủ repo. Các check bắt buộc là `Branch policy`, `Backend syntax`, `Backend tests`, `Frontend build`; cập nhật rule GitHub cùng với workflow. Số approval bắt buộc là 0 vì hiện không có reviewer lập trình độc lập; Chiến vẫn phải đọc diff và bằng chứng trước khi merge.

Repo [ATI_Project](https://github.com/VinhDat267/ATI_Project) gợi ý cách dùng nhánh feature, PR template, CI và phân biệt bằng chứng chạy cục bộ với chạy dịch vụ thật. Quy trình này rút gọn cho một người; không sao chép module ownership của nhóm nhiều lập trình viên.
