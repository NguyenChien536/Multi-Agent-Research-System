# Synthia — Multi-Agent Research System

Hỗ trợ nghiên cứu từ câu hỏi/nguồn đến bản thảo bài báo có bằng chứng. Cấu hình API và model trên giao diện. Người nghiên cứu kiểm tra kết quả trước khi sử dụng hoặc công bố.

## Chạy local

Cần Docker Desktop và Internet cho provider. Chỉ dùng **docker-compose.yml**, một Dockerfile cho mỗi ứng dụng; PostgreSQL/Redis không mở cổng ra ngoài, gateway chỉ bind loopback.

```powershell
# Chỉ lần đầu trên máy mới; không ghi đè cấu hình đã có.
.\scripts\release.ps1 -Action init
# Build source đã commit, migration và đợi healthy.
.\scripts\release.ps1 -Action start
.\scripts\release.ps1 -Action status
# Dừng, giữ dữ liệu.
.\scripts\release.ps1 -Action stop
```

`status` in địa chỉ đang dùng. Máy mới mặc định http://127.0.0.1:3080; máy đã chuẩn bị demo dùng cấu hình active local. Không dùng `down -v` để cập nhật.

## Cấu hình và dùng

1. Đăng nhập, mở **Settings → API & model**.
2. Chọn dịch vụ, nhập key và model ID rồi lưu. Key được mã hóa trên server, không trả lại trình duyệt. Để trống key khi sửa model để giữ key cũ.
3. Bài mới tự dùng bản sao cấu hình mặc định. Đổi mặc định không đổi các bài đã tạo.
4. Trong Settings của workspace, chọn **Bài hiện tại** để đổi kết nối khi bài không RUNNING/QUEUED, áp dụng mặc định hoặc lưu kết nối bài làm mặc định.
5. Theo dõi Agent Monitor, kiểm nguồn/bằng chứng, đọc cảnh báo và bản thảo trước khi xuất.

Hỗ trợ dịch vụ có giao thức chat OpenAI-compatible, không bắt buộc dùng dịch vụ OpenAI. Chọn đúng địa chỉ và model của dịch vụ cấp key. Quản trị viên thêm API root tin cậy qua CUSTOM_LLM_API_ROOTS. Không gửi key vào chat/issue/Git.

**Miễn phí:** API key không chứng minh tài khoản miễn phí. Giá hiển thị là ước tính, không phải hóa đơn. OpenRouter giá 0 yêu cầu `:free` hoặc `openrouter/free` và lọc provider giá 0. Kết nối riêng không tự dùng key search/embedding của máy chủ. Giới hạn token/lượt gọi/thời gian vẫn áp dụng; đổi model không xóa ngân sách đã dùng của bài.

## Ba luồng

| Loại | Đầu vào | Đầu ra và giới hạn |
|---|---|---|
| REVIEW | Câu hỏi, tùy chọn PDF | Tổng quan có mục con, nguồn và giới hạn; không tự nhận systematic review |
| EMPIRICAL_COMPUTATIONAL | Câu hỏi và CSV số | Routine tabular_regression_v1: Ridge/mean baseline, split 80/20 seed 42, MAE/RMSE/R², figure, journal, repeatability và gói tái lập; không chạy mã AI tùy ý |
| EMPIRICAL_HUMAN | Protocol; sau đó CSV/TXT và nguồn gốc kết quả | Lưu checkpoint chờ dữ liệu; không tự làm lab, tuyển người, phê duyệt đạo đức hoặc xác minh độc lập dữ liệu người dùng |

Bài đang chờ không giữ worker; có thể làm bài khác. Mặc định tối đa 2 RUNNING/người dùng. Nguồn được tìm thấy chưa chắc đủ hỗ trợ luận điểm. Thiếu bằng chứng phải dừng, thu hẹp hoặc nêu hạn chế, không dựng số liệu/reference.

## Kiến trúc và code

Browser → Next.js → FastAPI → PostgreSQL/outbox → Redis → Celery → LangGraph → providers/tools → evidence/report/artifacts.

Modular monolith, API/worker là tiến trình riêng; mỗi agent là vai trò trong graph. PostgreSQL giữ checkpoint; worker dùng claim/lease/attempt, outbox hỗ trợ gửi lại job. Không cam kết exactly-once cho provider calls.

| Đường dẫn | Trách nhiệm |
|---|---|
| backend/app/api, schemas | HTTP, auth/ownership, hợp đồng dữ liệu |
| backend/app/services | Settings/key, budget, evidence, manuscript, thí nghiệm, export |
| backend/app/agents | State, nodes, routing và research/revision loops |
| backend/app/tools, models, alembic | Search/retrieval, persistence và migration |
| frontend/src/app, components, lib/api.ts | Settings, workspace, monitor và HTTP client |
| backend/tests, frontend/tests, .github/workflows | Regression và CI |

## Kiểm thử, backup, demo

Backend tests bắt buộc database riêng có tên chứa `test`; CI migration rồi chạy pytest. Không test trên dữ liệu làm việc. Frontend: `npm ci`, `npm test`, `npm run build` trong frontend. Docker build cũng kiểm TypeScript và Next.js production.

```powershell
.\scripts\release.ps1 -Action backup
# Chỉ restore vào project mới; không ghi đè bản demo.
.\scripts\release.ps1 -Action restore -Project synthia-restore-check -Port 3083 -BackupPath '<backup folder>'
```

Giữ nguyên APP_SECRET_KEY khi phục hồi để đọc key mã hóa và phiên. Backup chứa dữ liệu riêng, giữ ngoài Git. Không xóa volumes, artifact nghiên cứu hoặc tài liệu người dùng khi dọn cache.

- [Hiểu code và demo ba loại](docs/technical/demo-guide.md)
- [Vận hành và phục hồi](docs/technical/local-release.md)
- [System Design](docs/architecture/system-design.md)
- [SRS](docs/requirements/SRS.md)

Bố cục đầy đủ không bảo đảm chất lượng Q1, kết quả đúng hoặc được nhận đăng. Tests/build không thay thế chạy provider và đọc bài thật. NEEDS_REVIEW nghĩa là còn kiểm tra chưa khép.
