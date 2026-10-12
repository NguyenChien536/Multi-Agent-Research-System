# Biên bản kiểm tra baseline kỹ thuật

**Ngày kiểm tra:** 27/09/2026<br>
**Phạm vi:** Docker Compose, PostgreSQL/pgvector, Redis/Celery, FastAPI, Alembic, LangGraph compile và routing.<br>
**Môi trường:** Windows + Docker Desktop; backend image chạy Python 3.11.<br>
**Mục đích:** Xác nhận nền tảng kỹ thuật trước khi mở thêm tính năng. Đây là smoke verification, không phải nghiệm thu MVP hay production.

> **Ghi chú 08/10/2026:** Bảng dưới giữ nguyên evidence lịch sử. Lượt rà soát planning mới chỉ đọc source và sửa tài liệu; chưa chạy lại Docker/DB/provider. Migration head trong source nay khác baseline; không hiểu kết quả cũ là trạng thái DB hiện tại.

> **Lượt xác minh mới 12/10/2026:** Đã chạy lại trên Docker Desktop sau khi người dùng bật Docker. Kết quả bên dưới là evidence mới nhất cho baseline P0; các kết quả ngày 27/09 chỉ còn giá trị lịch sử.

## Kết quả xác minh ngày 12/10/2026

| Hạng mục | Kết quả thực tế | Giới hạn |
|---|---|---|
| Docker Compose | `docker compose config --quiet` đạt; PostgreSQL, Redis, API và worker chạy ổn định. | Chưa kiểm tra tải hoặc cấu hình triển khai production. |
| PostgreSQL/pgvector | Chạy migration trên PostgreSQL tạm, database rỗng đến `a1b2c3d4e5f6 (head)`; DB dự án hiện tại cũng ở head. | Database tạm chỉ dùng để kiểm tra migration và đã dừng; không xóa volume dự án. |
| API | `GET /api/v1/health` trả HTTP 200 sau khi thay image. | Health chỉ xác nhận API có phản hồi. |
| Celery | `celery -A app.worker inspect ping --timeout=10` nhận `pong` từ worker sau khi rebuild từ lockfile. | Chưa chứng minh dispatch/retry của một workflow dùng provider thật. |
| Backend tests | `python -m pytest -q tests`: **2 passed**, 3 deprecation warnings. | Cả 2 bài test dùng provider/node giả; suite hiện còn nhỏ và không phải provider-backed E2E. |
| Backend image | Build thành công từ `backend/requirements.lock.txt`; API và worker khởi động với image mới. | Lockfile mới khóa phiên bản hiện được resolver chọn; cần tiếp tục pin/cập nhật có kiểm soát khi đổi dependency. |
| Python local và Docker | Đã đồng bộ `.python-version`/`requires-python` về 3.11; `uv lock --check --python 3.11` đạt; `uv run --locked --python 3.11 python --version` trả `Python 3.11.16`. | Máy Windows gọi `python` trực tiếp vẫn bị Microsoft Store alias; dùng `uv run` hoặc Docker theo hướng dẫn. |
| Frontend | `npm ci`, `npm run lint`, `npm run build` đều đạt với Next.js 15.5.27. `npm audit --omit=dev` báo 0 vulnerabilities. | `npm audit` toàn bộ vẫn cảnh báo ở dependency phát triển (Tailwind/ESLint); không ép nâng Tailwind major trong P0. FE hiện vẫn là mẫu, chưa xác minh tích hợp API. |

Các chỉnh sửa cần thiết để khép P0: đồng bộ Python root/backend về 3.11; thêm lockfile backend và dùng nó trong Docker/CI; tạo `frontend/package-lock.json` để `npm ci` tái lập được; nâng Next.js/ESLint config lên 15.5.27 để production build hoạt động với API route params hiện tại; bỏ tải font Google trong build để không phụ thuộc mạng ngoài. Những thay đổi này chưa chứng minh chất lượng luồng nghiên cứu.

Các lệnh chính đã chạy:

```powershell
docker compose config --quiet
docker compose build backend
docker compose up -d backend worker
docker compose exec -T backend alembic current
docker compose exec -T -e LANGSMITH_TRACING=false -e LANGCHAIN_TRACING_V2=false backend python -m pytest -q tests
docker compose exec -T worker celery -A app.worker inspect ping --timeout=10
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
cd frontend; npm ci; npm run lint; npm run build; npm audit --omit=dev
cd ..; uv lock --check --python 3.11; uv run --locked --python 3.11 python --version
```

**P0 status: Verified for Python/dependency alignment, reproducible builds, clean DB migration, and current baseline tests.** Chưa đạt các gate của P1/P2 và chưa chạy một research workflow thật với provider.

## Kết quả lịch sử ngày 27/09/2026

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

## Các mục còn chưa xác minh tính đến 12/10/2026

- Chưa chạy research task end-to-end với LLM/Tavily thật. Cần xác nhận provider, API key và ngân sách trước khi gọi dịch vụ có thể tính phí.
- Chưa xác minh citation/evidence lineage, chất lượng nội dung, research loop có dữ liệu thật, Celery retry/redelivery, cancellation, idempotency/outbox hoặc xử lý lỗi lúc dispatch.
- Auth, ownership cơ bản, đăng nhập, task start và chặn đọc chéo owner đã được kiểm tra trong backend suite hiện có; chưa coi đây là nghiệm thu toàn bộ bảo mật.
- Frontend mới qua lint/build; chưa chạy trình duyệt, chưa kết nối API. SSE, tải file, hiệu năng và hardening production chưa xác minh.
- Migration từ database rỗng đã được kiểm tra trong PostgreSQL tạm. Chưa kiểm thử upgrade từ mọi phiên bản DB đang được sử dụng hoặc downgrade.

## Bước tiếp theo

1. Sang P1: hoàn thiện lifecycle/run và dispatch bền vững; tập trung vào lỗi commit task thành công nhưng enqueue thất bại, duplicate delivery, cancel và quota RUNNING.
2. Tăng backend tests cho các chuyển trạng thái, dispatch failure/redelivery, worker restart và task A chờ trong lúc task B chạy.
3. Chỉ sau khi các test P1 đạt mới mở P2 để hoàn thiện research path; provider-backed run cần có cap chi phí riêng.
4. Ghi lệnh và kết quả vào biên bản này sau mỗi gate; không đánh dấu provider E2E đạt dựa trên test dùng fake node/provider.

## An toàn thông tin

Không đưa API key, mật khẩu hoặc nội dung `.env` vào tài liệu, prompt hay log được chia sẻ. Tài liệu chỉ ghi trạng thái và output không nhạy cảm.
