# Architecture Decision Records (ADR)

Thư mục này lưu trữ các quyết định kiến trúc quan trọng của dự án. Mỗi quyết định cần theo format chuẩn dưới đây.

## Mẫu ADR (Template)
```md
# ADR-00X: Tên quyết định
**Trạng thái:** Đề xuất / Đã chấp thuận / Đã hủy
**Ngày:** YYYY-MM-DD
**Bối cảnh:** Vấn đề cần giải quyết là gì?
**Quyết định:** Chọn giải pháp nào?
**Lý do:** Tại sao chọn giải pháp này (dựa trên bằng chứng)?
**Hệ quả (Consequences):** Điều gì tốt lên, điều gì tệ đi (chi phí, độ phức tạp)?
```

## Danh sách các Quyết định Kiến trúc

1. **[ADR-001: Image Discovery và Serper.dev Provider bổ sung](ADR-001-image-search-provider.md)**
   - Trạng thái: Đã chấp thuận
   - Quyết định: Serper.dev là provider bổ sung tùy chọn khi các trang đã thu thập chưa có ảnh phù hợp; API key do backend/dự án quản lý. Ảnh không tham gia evidence/citation.
2. **[ADR-002: Lược đồ dữ liệu Claim-Evidence Junction Table và Citation.chunk_id](ADR-002-db-migration-claim-evidence.md)**
   - Trạng thái: Đã chấp thuận
   - Quyết định: Cấu trúc lại quan hệ nhiều-nhiều cho `ClaimEvidence` và bổ sung `chunk_id` vào bảng `Citation` bằng migration mới để đảm bảo tính toàn vẹn tham chiếu (traceability).

3. **[ADR-003: Hỗ trợ đa phương pháp và ranh giới thực nghiệm có người giám sát](ADR-003-research-execution-modes.md)**
   - Trạng thái: Chấp thuận nguyên tắc sản phẩm; runner vendor/implementation còn mở.
   - Quyết định: Routine tính toán được duyệt chạy trong isolated boundary; human-led studies dừng ở protocol, chờ data bền vững, không sinh Results giả.
