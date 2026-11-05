# Synthia — Multi-Agent Research System

Hỗ trợ nghiên cứu từ câu hỏi/nguồn đến bản thảo bài báo có bằng chứng. Cấu hình API và model trên giao diện. Người nghiên cứu kiểm tra kết quả trước khi sử dụng hoặc công bố.

## Hai môi trường local

Cần Docker Desktop. Một **docker-compose.yml** có hai profile, mỗi môi trường có database, Redis, file và secret riêng. Mỗi ứng dụng vẫn có một Dockerfile.

| | Dev — lập trình | Prod local — demo |
|---|---|---|
| Web | http://127.0.0.1:3000 | http://127.0.0.1:3082 trên máy hiện tại |
| Nhóm Docker | synthia-dev | synthia-workflow-check trên máy hiện tại |
| Code | FE/API tự reload | Image cố định, không mount source |
| Tài khoản và API key | Đăng ký, lưu Settings riêng | Giữ dữ liệu/cấu hình demo hiện có |

```powershell
# Dev: init một lần, start dùng code đang sửa.
.\scripts\dev.ps1 -Action init
.\scripts\dev.ps1 -Action start
.\scripts\dev.ps1 -Action status
# Sau khi sửa agent/tool và các job dev đã xong:
.\scripts\dev.ps1 -Action restart-worker
.\scripts\dev.ps1 -Action stop

# Demo: bật lại đúng image đã chốt, không build source đang sửa.
.\scripts\release.ps1 -Action start
.\scripts\release.ps1 -Action status
.\scripts\release.ps1 -Action stop

# Đưa code mới sang demo: test và commit trước.
.\scripts\release.ps1 -Action deploy
```

Máy mới: chạy release `init`, rồi `deploy` một lần; sau đó dùng `start`. Máy hiện tại đã có bản demo, không init lại. `status` in URL thực tế; máy mới mặc định cổng 3080. Không dùng `down -v` hoặc chép secret/database demo sang dev. Database/Redis không publish cổng; dev API có docs tại http://127.0.0.1:8000/api/v1/docs.

Kiểm hai môi trường đang chạy, không gọi provider: `python scripts/check-environments.py`. Script tạo tài khoản/bài tạm rồi tự xóa đúng dữ liệu thử nghiệm đó. Xem [hướng dẫn vận hành](docs/technical/local-release.md).

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
| backend/app/prompts/templates | Chỉ dẫn model ở file txt; code nạp qua render_prompt, không hard-code các prompt dài |
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
