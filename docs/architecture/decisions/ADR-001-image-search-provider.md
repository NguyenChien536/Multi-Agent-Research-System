# ADR-001: Image Discovery Provider and Report Image Flow

| Thuộc tính | Giá trị |
|:---|:---|
| **ID** | ADR-001 |
| **Ngày** | 2026-10-01 |
| **Trạng thái** | ✅ Accepted |
| **Người quyết định** | Chiến (Tech Lead) |
| **Phạm vi** | Image enrichment sau bản nộp; biểu đồ từ experiment thuộc core theo SRS v4.0 |
| **Liên quan** | System Design; SRS rút gọn FR-14; Product Assessment |

---

## Bối cảnh và yêu cầu

Báo cáo nghiên cứu có thể được trình bày trực quan hơn bằng ảnh minh họa. Tính năng này phải giảm thao tác của người dùng và không làm ảnh lẫn với bằng chứng nghiên cứu.

- Ưu tiên ảnh được tham chiếu trong các trang nguồn đã thu thập/fetch cho task.
- Nếu chưa đủ ảnh phù hợp, có thể gọi Serper.dev Google Images khi provider được cấu hình và còn quota/budget.
- Tự động lọc và đưa ảnh phù hợp vào phần báo cáo; không yêu cầu người dùng duyệt từng ảnh. Sau đó người dùng có thể xóa từng ảnh hoặc tắt toàn bộ ảnh trước khi export.
- Lưu URL ảnh và trang chứa ảnh, tiêu đề/caption, attribution/tác giả nếu có, provider, license status, thời điểm thu thập và vị trí trong report.
- Ảnh chỉ là minh họa; không tạo Evidence/Claim/Citation từ ảnh.
- Không tự suy ra quyền tái sử dụng từ kết quả tìm kiếm. Nếu license không rõ, lưu `Unknown` và hiển thị cảnh báo cùng liên kết nguồn. Không dùng ảnh nếu điều khoản nguồn/provider cấm sử dụng.
- Image discovery thuộc roadmap sau bản nộp theo SRS v4.0; quyết định này không yêu cầu triển khai ngay.

ADR này chỉ nói về ảnh minh họa lấy ngoài hệ thống. Biểu đồ tính từ dataset thật là `ResearchArtifact` của `AnalysisRun`, thuộc FR-07/FR-11 core và có thể làm evidence cho kết quả; không đi qua Serper hoặc `ReportImage`.

## Các lựa chọn

### A. Tự trích ảnh từ các trang đã thu thập, Serper.dev làm nguồn bổ sung — Chọn

Tận dụng trước ảnh tham chiếu có trong HTML/metadata của trang đã fetch. Chỉ khi kết quả thiếu ảnh đạt tiêu chí liên quan/chất lượng thì gọi Serper để lấy ứng viên bổ sung.

**Ưu điểm:** giảm truy vấn và phụ thuộc provider; dùng lại ngữ cảnh nghiên cứu; Serper mở rộng độ phủ khi trang nguồn không có ảnh phù hợp.

**Đánh đổi:** ảnh trong nguồn có thể thiếu, URL có thể hỏng/hotlink bị chặn, metadata license có thể không đầy đủ; Serper phát sinh chi phí sau quota miễn phí và cũng không xác nhận quyền sử dụng ảnh.

### B. Chỉ dùng provider ảnh riêng

Không chọn làm luồng mặc định vì sẽ gọi thêm dịch vụ ngay cả khi trang nguồn đã có ảnh phù hợp, tăng chi phí và phụ thuộc.

### C. Chỉ dùng ảnh sinh bằng AI

Không chọn trong ADR này. Đây là luồng sản phẩm/provider khác; nếu bổ sung sau này, ảnh phải có nhãn `AI-generated` và không được dùng làm evidence.

## Quyết định

Chọn lựa chọn A. **Serper.dev là provider bổ sung tùy chọn, không phải bước bắt buộc của mọi research task.** Worker ưu tiên ảnh từ các trang đã thu thập; chỉ gọi endpoint Google Images của Serper khi chưa đủ ứng viên phù hợp, task cho phép ảnh và budget/quota còn.

Luồng người dùng mặc định tự thêm ảnh sau khi report draft qua kiểm tra citation. Người dùng không bị hỏi chọn từng ảnh; họ có thể bỏ từng ảnh hoặc tắt ảnh sau khi xem report. Export chỉ dùng ảnh vẫn đang được include.

## Vận hành, chi phí và bảo mật

- `SERPER_API_KEY` là cấu hình backend/secret tùy chọn; không gửi key xuống trình duyệt, không commit vào Git.
- Mô hình mặc định dùng một key do dự án quản lý: quota và chi phí tính vào tài khoản dự án; người dùng cuối không phải mua key riêng. BYOK không thuộc phạm vi quyết định này.
- Đặt giới hạn số truy vấn/kết quả theo task và project; ghi nhận usage, lỗi, latency và chi phí ước tính. Nếu key thiếu, provider lỗi hoặc quota/budget hết, tiếp tục báo cáo bằng ảnh từ trang nguồn nếu có, nếu không thì hoàn tất không ảnh.
- Giá, quota, số credit theo endpoint và điều khoản có thể thay đổi. Kiểm tra trang giá/tài liệu Serper chính thức tại thời điểm cấu hình hoặc mua credit; không hardcode giá vào ứng dụng hay coi số liệu cũ là cam kết.
- Kết quả provider và URL ảnh là dữ liệu không tin cậy. Chỉ hiển thị HTTPS URL đã qua validation; nếu server fetch ảnh cho PDF, validate scheme/host, MIME, kích thước và redirect, chặn private/loopback/link-local IP và bảo vệ chống SSRF. Không lưu bytes ảnh theo quyết định này.
- Khi browser hiển thị ảnh trực tiếp từ host bên ngoài, host đó nhận request từ browser người dùng; phải thông báo trong privacy notice. Nếu triển khai proxy ảnh phía server sau này, cần thiết kế riêng cho SSRF, giới hạn kích thước/timeout và cache.
- Hiển thị URL trang nguồn, attribution nếu có và license status. `Unknown` không đồng nghĩa với giấy phép cho phép tái sử dụng; ảnh có điều khoản cấm phải bị loại. Cảnh báo quyền sử dụng không thay thế kiểm tra terms.

## Hệ quả thiết kế dữ liệu

- Lưu ứng viên ảnh như `ResearchSource` với `source_type=IMAGE`; `url` là URL ảnh và `source_page_url` là trang chứa ảnh. Lưu provider, attribution, license status, title/caption và ngày truy xuất khi có.
- Dùng quan hệ mục tiêu `ReportImage` (hoặc tên tương đương sau khi đối chiếu model) để gắn `ResearchSource` ảnh với report, section/position, inline marker, alt text/caption và trạng thái `is_included`. Renderer/UI chỉ resolve marker qua các ảnh được include. Bỏ ảnh khỏi report bằng cách đổi trạng thái, không xóa provenance nguồn.
- Lưu cờ `include_images` ở cấu hình task/report. Cờ mặc định có hiệu lực khi tính năng image enrichment được bật; core bản nộp không bắt buộc image provider.
- ERD trong system-design là thiết kế mục tiêu. Cần migration/API acceptance criteria riêng trước khi gọi schema hoặc chức năng này là đã triển khai.

## Xem thêm

- [Serper.dev API Reference](https://serper.dev/api-reference)
- [Serper.dev Pricing](https://serper.dev/)
- [System Design](../system-design.md)
- [SRS rút gọn hiện hành](../../requirements/SRS.md)
- [ADR-002: ClaimEvidence và Citation.chunk_id](ADR-002-db-migration-claim-evidence.md)
