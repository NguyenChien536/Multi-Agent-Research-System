# Biên bản kiểm tra baseline kỹ thuật

**Ngày kiểm tra:** 27/09/2026<br>
**Phạm vi:** Docker Compose, PostgreSQL/pgvector, Redis/Celery, FastAPI, Alembic, LangGraph compile và routing.<br>
**Môi trường:** Windows + Docker Desktop; backend image chạy Python 3.11.<br>
**Mục đích:** Xác nhận nền tảng kỹ thuật trước khi mở thêm tính năng. Đây là smoke verification, không phải nghiệm thu MVP hay production.

> **Ghi chú 08/10/2026:** Bảng dưới giữ nguyên evidence lịch sử. Lượt rà soát planning mới chỉ đọc source và sửa tài liệu; chưa chạy lại Docker/DB/provider. Migration head trong source nay khác baseline; không hiểu kết quả cũ là trạng thái DB hiện tại.

## Kết quả

| Hạng mục | Kết quả | Giới hạn |
|---|---|---|
| Compose | `docker compose config --quiet` đạt; `docker compose up -d --build` build và khởi động đủ service | Cấu hình development, không phải deployment production. |
| Services | `backend`, `worker`, `postgres`, `redis` đều đang chạy; PostgreSQL và Redis báo `healthy` | Chưa kiểm tra load, restart recovery hoặc production hardening. |
| PostgreSQL/pgvector | PostgreSQL 16.15; extension `vector` tồn tại; các bảng nghiệp vụ có trong DB | Đây là volume đã có sẵn, chưa chứng minh migration chạy được từ database rỗng. |
| Alembic | `alembic current` báo `5ee074153cf3 (head)` | Không chạy upgrade vì DB đã ở head; chưa kiểm thử downgrade/upgrade trên DB sạch. |
| Redis/Celery | `redis-cli ping` trả `PONG`; Celery `inspect ping` nhận `pong` từ một worker | Chưa gửi research task thật vào worker. |
| FastAPI | `/api/v1/health` trả HTTP 200; `/api/v1/openapi.json` trả HTTP 200 | Health endpoint chỉ phản ánh API; không tự xác nhận toàn bộ workflow. |
| Task API | POST tạo task trả `PENDING`; GET theo ID đọc lại thành công; task kiểm tra đã được xóa | Chưa kiểm tra list, start, report, SSE, auth/ownership và lỗi truy cập chéo user. |
| LangGraph | Import trả `CompiledStateGraph`; 5 trường hợp smoke routing cho PASS/REVISE/NEED_MORE_DATA và giới hạn vòng lặp đạt | Chưa invoke toàn graph hoặc gọi LLM/Tavily. |
| Python source | `compileall` trong backend container thành công | Không thay thế unit/integration tests. |

## Lỗi baseline đã sửa

1. Backend và worker không khởi động do thiếu `greenlet` khi dùng SQLAlchemy async. `backend/requirements.txt` đổi thành `SQLAlchemy[asyncio]>=2.0.30`; rebuild thành công.
2. Worker khởi tạo `iteration_count`/`micro_loop_count`, nhưng graph dùng `current_iteration`/`current_micro_revision`. Worker nay gửi đúng key, cùng `max_iterations` từ task và `attempt_number`.

Tại thời điểm lập biên bản các thay đổi này chưa commit. Đến source review 08/10, chúng đã nằm trong lịch sử của `ebb525a`; trạng thái commit không thay đổi phạm vi runtime evidence ngày 27/09.

## Lệnh và bằng chứng đã chạy

Chạy tại thư mục gốc repository:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec -T redis redis-cli ping
docker compose exec -T postgres psql -U research_user -d research_db -Atc "SELECT version(); SELECT extname FROM pg_extension WHERE extname = 'vector';"
docker compose exec -T backend alembic -c /app/alembic.ini current
docker compose exec -T worker celery -A app.worker.celery_app inspect ping --timeout=5
docker compose exec -T backend python -m compileall -q app
```

Đã kiểm tra HTTP:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/v1/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/v1/openapi.json
```

Đã smoke-test POST/GET task qua `/api/v1/research`, rồi xóa task kiểm tra. Routing smoke-test chạy trong backend container với các state mẫu; các trường hợp được kiểm tra gồm `PASS → post_processor`, `REVISE → writer`, `NEED_MORE_DATA → macro_routing/researcher`, và dừng research khi đạt `max_iterations`.

## Chưa xác minh

- Chưa chạy research task end-to-end. Workflow có thể gọi LLM/Tavily và phát sinh chi phí; cần chốt provider, API key và trần chi phí trước khi chạy.
- Chưa xác minh citation/evidence lineage, độ đúng ngữ nghĩa, macro-loop có dữ liệu thật, retry/idempotency và trạng thái lỗi.
- Chưa kiểm tra auth/ownership; API hiện còn dùng `dummy_user_id`, chưa phù hợp cho người dùng thật.
- Chưa kiểm tra giao diện frontend, luồng SSE thật, hiệu năng, bảo mật production hoặc khởi tạo DB từ volume rỗng.
- Python local/root project đang khác backend Docker (3.14 so với 3.11); dependencies backend chưa được khóa đầy đủ để tái lập chính xác.

## Bước tiếp theo

1. Rà soát thay đổi theo từng phạm vi và dùng commit riêng cho implementation với documentation; tài liệu dự án được version cùng mã nguồn.
2. Chốt Python/dependency baseline có thể tái lập giữa local và Docker.
3. Ưu tiên auth/ownership và trạng thái task trước khi mở cho người dùng khác.
4. Viết/hoàn thiện kiểm thử không gọi provider ngoài cho state, routing, lỗi và citation validator.
5. Chạy một workflow end-to-end có giới hạn chi phí, lưu bằng chứng command/result, rồi mới đánh dấu search → evidence → report hoàn tất.

## An toàn thông tin

Không đưa API key, mật khẩu hoặc nội dung `.env` vào tài liệu, prompt hay log được chia sẻ. Tài liệu chỉ ghi trạng thái và output không nhạy cảm.
