# Biên bản kiểm tra baseline kỹ thuật

## R2 ngày 24/10/2026 — issue #41

- Giới hạn server/schema theo SRS: tối đa 40 LLM calls, 100.000 input tokens, 50.000 output tokens, 2 USD ước tính và 900 giây chạy chủ động. Usage/reservation lưu trong JSON budget của task nên không reset khi worker retry; reserve/reconcile được khóa theo task.
- Mỗi LLM fallback và embedding retry đặt chỗ riêng; Tavily search được chặn trước request. Provider model/giá không nhận diện được sẽ bị chặn. PDF upload chỉ parse/chunk locally; worker tạo embedding trong ngân sách trước khi phân tích.
- Cancel/stale attempt/lease hết hạn chặn stage hoặc provider call kế tiếp. Budget exhaustion đưa task sang `NEEDS_REVIEW`; lỗi không chắc provider đã nhận request thì giữ nguyên khoản đặt chỗ. Request provider đang bay có thể hoàn tất, nhưng worker không dùng kết quả đó để phát sinh bước tiếp theo sau khi nhận diện cancel.
- DB test riêng migrate từ rỗng lên `d1e2f3a4b5c6`; `pytest -q`: **109 passed, 4 warnings trong 34.38s**. Gồm kiểm tra giới hạn đồng thời, cap chi phí/thời gian/search, fallback, hủy/stale/lease, embedding retry và không deadlock khi lưu nguồn mới. Provider được giả lập; không dùng DB dev.
- `docker compose build backend`, `docker compose config --quiet`, Python `compileall` và `GET /api/v1/openapi.json` đạt. PR #42 đạt 5/5 CI và đã squash-merge vào `develop` tại `eacdb2b`; chưa chạy provider thật hoặc browser E2E, nên chưa đánh dấu G1/G2 đạt.
- Chi phí search hiện dùng **ước tính mặc định 0.01 USD/request**, không phải giá hóa đơn cam kết. Phải kiểm tra/cấu hình theo gói Tavily trước khi chạy pilot có phí. Main chưa thay đổi.

## R1 ngày 23/10/2026 — issue #39

- Đã sửa A01/A02 ở audit 22/10 trên branch `bugfix/39-authenticated-fieldwork-intake`: profile gửi bearer/401 xử lý session; intake cần file/provenance, kiểm owner/task/type/file, UUID lưu JSON hợp lệ; UI có upload/chọn kết quả CSV/TXT và trạng thái đang tải. Kết quả người dùng không được gắn nhãn xác minh độc lập.
- Database tạm `synthia_r1_test_cdd7b380`: migrate từ rỗng đến `d1e2f3a4b5c6`, **98 passed, 6 warnings trong 37.51s**; đã xóa DB/artifacts tạm sau kiểm tra. Provider giả; không chạy job người dùng hoặc test trên DB dev.
- PR #40 đạt **5/5 CI** trên candidate 1ddd020 và đã merge develop tại **baac5ba** ngày 23/10; issue #39 đã đóng. CI build/typecheck và frontend tests xác minh cả điều chỉnh cuối cùng của banner WAITING. Không thay đổi main.
- **5 frontend regression tests đạt** bằng `npm test`: protected auth/me, login/register, session expiry, failed login và authenticated multipart upload. Frontend CI đã thêm chạy suite này.
- Ca mới gồm thiếu file/provenance, UUID, sai owner/cùng owner khác task, sai loại artifact/research, file mất/sai kích thước, file malformed/quá lớn/quota, và hai resume đồng thời chỉ tạo một outbox event.
- Còn phải nghiệm thu browser/provider E2E của release và các yêu cầu R2–R8. Chưa có durable checkpoint/versioned decision (R3), ingest job riêng (R6) hoặc sandbox production. PR/CI được ghi cập nhật tại Roadmap; không đánh dấu G1/G4 hoàn thành chỉ từ R1.

<a id="kiem-tra-2026-10-22"></a>

## Audit ngày 22/10/2026 — chức năng hiện có và điều kiện production

**Phạm vi:** đọc code/CI/docs, kiểm runtime local, chạy lại toàn bộ backend tests và frontend lint/build, thử thêm các ca chưa có trong suite. Source backend: `3bbeb01`; frontend gồm thay đổi local chưa commit tại `research/[id]/page.tsx` và `MarkdownViewer.tsx`. Chưa chạy provider mới hoặc thử giao diện bằng trình duyệt trong lượt này. Audit sửa tài liệu/kế hoạch, **chưa sửa các lỗi source bên dưới**.

**Kết luận:** nền tảng local và các ca regression đang đạt; không đủ căn cứ xác nhận mọi chức năng ổn. G1–G7 chưa khép; chưa sẵn sàng production. Các chỉ dẫn “bước tiếp theo” ở phần lịch sử phía dưới chỉ có giá trị tại ngày ghi. Kế hoạch hiện hành nằm ở [Implementation Plan](implementation-plan.md).

### A. Kết quả kiểm tra thực tế

| Hạng mục | Kết quả 22/10 | Giới hạn |
|---|---|---|
| GitHub CI tại `3bbeb01` | [Run 39783342134](https://github.com/NguyenChien536/Multi-Agent-Research-System/actions/runs/39783342134): 5/5 jobs thành công | Không bao gồm frontend local chưa commit; không phải provider/browser E2E |
| Migration từ database rỗng | `alembic upgrade head` exit 0 đến `d1e2f3a4b5c6` | Chưa chứng minh upgrade mọi dữ liệu release cũ/rollback |
| Toàn bộ backend suite | `python -m pytest -q tests`: **74 passed, 6 warnings, 24.37s** | Provider được giả lập; không chứng minh chất lượng model, chạy broker crash thật hoặc mức tải |
| Frontend local | `npm run lint` và `npm run build` exit 0; Next.js 15.5.27 | Build/typecheck không thay việc sử dụng trên trình duyệt |
| Frontend dependencies | `npm audit --omit=dev --json`: **0 vulnerabilities**, exit 0 | Theo advisory database lúc chạy; không bao gồm dev dependencies, backend hoặc container/system packages |
| Compose/API/UI | `docker compose config --quiet` đạt; health API và trang `/login` trả **200** | Compose là development; health API trả trạng thái tĩnh, chưa phải DB/Redis readiness |
| PostgreSQL | DB dev tại migration head `d1e2f3a4b5c6` | Chỉ đọc; không chạy suite hoặc migration phá dữ liệu trên DB dev |
| Redis/Celery | Redis **PONG**; Celery **1 node pong**; broker list `celery` có **0** phần tử | Chỉ snapshot, không phải soak test hay kiểm tất cả queue |
| Probe FE `/auth/me` | Có session token giả nhưng request **không có Authorization**; `/research` có header | Tái hiện bằng chính `api.ts` đã transpile với stub fetch; chưa sửa |
| Probe intake không file | `EMPIRICAL_HUMAN` ở WAITING_USER_DATA, chỉ sample_size/method_notes/results_summary → **HTTP 200, QUEUED** | Không có artifact/provenance vẫn được nhận; chưa phù hợp SRS |
| Probe intake có UUID file | Nạp `file_artifact_id` → **StatementError / TypeError: Object of type UUID is not JSON serializable** | ASGI probe bật raise_app_exceptions nên nhận exception trực tiếp; đây là lỗi server chưa được xử lý, không phải response validation hợp lệ |

Database test `ati_audit_test_8e338c793c` và database probe `ati_audit_test_56dd988252` được tạo riêng, có pgvector, rồi đã đóng kết nối/xóa sau kiểm tra. Artifact test đặt trong thư mục tạm riêng; không xóa volume dự án. Hai probe không khởi động app lifespan/dispatcher và không gọi graph/provider. Không gửi/replay research job của người dùng.

Warnings hiện thấy ở langchain-community cache, Pydantic Config, passlib/crypt, tên HTTP 422 của Starlette và google-genai/aiohttp. Đây là nợ tương thích cần theo dõi, không phải 6 test thất bại. Không tự nâng major dependency trong audit này.

### B. Findings và cách xử lý

Mức **Cao**: chặn nghiệm thu luồng liên quan hoặc phát hành cho người ngoài. **Vừa**: cần hoàn thiện đúng contract trước khi đóng gate. Đây không phải chứng nhận an toàn hoặc audit bảo mật đầy đủ.

| ID / mức | Bằng chứng trong source | Tác động | Hành động trong plan |
|---|---|---|---|
| A01 · Vừa | [api.ts](../../frontend/src/lib/api.ts): fetcher bỏ token cho mọi endpoint `/auth/`, gồm `/auth/me` | Client không lấy được thông tin tài khoản qua helper này; không có nghĩa mọi lần login đều lỗi | R1: chỉ bỏ ở route công khai; test helper và session hết hạn |
| A02 · Cao | [research.py](../../backend/app/api/v1/endpoints/research.py), `resume_research_with_data`: lưu `payload.model_dump()` vào JSONB; schema cho artifact/provenance optional; hai probe A đã tái hiện | Có file gây lỗi serialize; không file vẫn resume dù thiếu căn cứ thực nghiệm; chưa kiểm artifact đúng owner/task/READY | R1: JSON serialization, validate evidence/provenance/type/version; regression file giả/sai owner. Chưa chứng minh có đường đọc file trái phép qua lỗi này |
| A03 · Cao | [worker.py](../../backend/app/worker.py) initial state không đưa budget_config vào guard; [nodes.py](../../backend/app/agents/nodes.py) gọi ainvoke trực tiếp; graph chỉ có giới hạn vòng | Có ghi estimated cost không bảo đảm chặn trước khi vượt cap; retry/fallback/search/embed cần cùng ledger | R2: gateway reserve/reconcile + quota server; không chạy paid smoke mới trước khi guard đạt |
| A04 · Cao | nodes `_record_progress` bỏ kết quả False từ [progress.py](../../backend/app/services/progress.py); cancel chỉ đổi state/lease/outbox | Graph đã chạy có thể tiếp tục tool/provider sau cancel. Worker có guard khi ghi report cuối, nhưng guard đó không chặn mọi side effect | R2: check cancel/attempt/lease trước call và write; test cancellation giữa stages |
| A05 · Cao | [graph.py](../../backend/app/agents/graph.py) `workflow.compile()` không checkpointer; worker invoke lại initial state | Có trạng thái WAITING trong DB nhưng chưa phải resume đúng checkpoint/node/version; có thể làm lại stage đã làm | R3: durable run/checkpoint và decision version; side effect idempotency; crash/resume tests |
| A06 · Cao | nodes experiment_runner gọi routine và verify_repeatability đồng bộ; sau đó mới dựng PLAN_FROZEN/STARTED; [experiment_runner.py](../../backend/app/services/experiment_runner.py) gọi lại routine cùng process | Chặn worker/event loop; crash trước persist có thể mất bằng chứng attempt; kiểm tính xác định cùng process chưa phải execution độc lập | R4: persist journal trước dispatch, runner có giới hạn và kill, rerun manifest ở execution mới |
| A07 · Cao | nodes critic đưa `draft[:3000]` vào prompt; protocol human-led đi vào WAITING trước luồng review đầy đủ | Phần Methods/Results/cuối bài có thể chưa được Critic đọc; không thể gọi là đã review toàn bộ | R5: review theo section/evidence và hợp nhất verdict; tests lỗi ở cuối bài/protocol |
| A08 · Vừa | research upload await parse/embed trong request; delete DB trước rồi bỏ qua lỗi cleanup; cache Redis LLM cấu hình global | Timeout/đứt request khó phục hồi; có thể còn file/cache sau xóa; chưa chứng minh tenant/retention policy của cache | R6/R8: ingest job, tombstone/retry cleanup; tắt private cache hoặc scope/invalidate đúng owner/task/version, kiểm log redaction |
| A09 · Vừa | [report.py](../../backend/app/models/report.py): unique research_task_id, quan hệ một report/task; chưa có Q&A/report version contract hoàn chỉnh | Chưa nghiệm thu sửa bài giữ bản cũ hoặc hỏi theo version; không đánh dấu P6 hoàn thành | R7: ReportVersion/run lineage và version-scoped Q&A/export |
| A10 · Cao khi deploy | [Dockerfile.release](../../backend/Dockerfile.release) cài requirements.txt; dev Compose publish DB/Redis ra host, DEBUG và secret dev; release workflow chỉ publish backend image | Artifact release có thể khác bản đã test; chưa có môi trường đủ điều kiện phục vụ người dùng ngoài | R8/P8: lockfile, secrets/network/readiness, cùng image digest staging→prod; restore/rollback/pilot |

**Sai khác contract cần khép:** SRS quy định CSV 5 MiB/20.000 hàng/30 cột; parser hiện tối đa 10.000 hàng/51 cột và route dùng giới hạn upload chung 10 MiB. SRS cap 40 LLM calls/2 USD/15 phút, API budget schema hiện cho giá trị khác và trần client rộng hơn. R2/R4 phải thống nhất server/schema/UI/tests theo SRS trước khi nghiệm thu. Không nâng giới hạn hàng trước khi đo runner; input chưa hỗ trợ phải báo rõ, không nhận rồi treo. Protocol/metadata đơn thuần không được coi là Results đã xác minh.

### C. Evidence lịch sử và dữ liệu đang tồn tại

- Biên bản 18/10 phía dưới ghi một lượt provider thật. Audit chỉ đọc lại task `ec0de102-517f-4706-ae51-d46d21e7987e`: còn COMPLETED, report **1.325 từ**, **9 citations**, **0 AgentRun**. Điều này xác nhận report còn lưu, không xác minh lại model/keys/chi phí hoặc toàn bộ citation semantics của lần chạy đó.
- Không xóa ghi nhận lịch sử hoặc viết lại thành “chưa từng chạy provider”. Đồng thời, một report cũ không thay smoke trên release candidate hiện tại; phải thu evidence đủ hơn trong lần tới.
- DB dev còn task QUEUED trong khi broker queue rỗng và các PLANNING/WAITING cũ. Cần đối soát owner/run/outbox/lease trước xử lý; không auto-resume/xóa chỉ vì trạng thái cũ. DB chứa nhiều dữ liệu thử nên tổng số COMPLETED không dùng làm benchmark thành công.
- Health/pong cho biết service phản hồi tại thời điểm kiểm. Chưa có load/soak/fault/restore test hoặc kiểm độc lập chất lượng bài báo; không gọi hệ thống “ổn hết” dựa vào các số này.

### D. Chạy lại kiểm tra an toàn

1. Tạo database mới có tên chứa `_test_` bằng psycopg, enable vector; tạo artifact directory tạm. Không dùng research_db.
2. Trong **tiến trình test riêng**, trỏ DATABASE_URL, POSTGRES_SYNC_URL, TEST_DATABASE_URL và TEST_POSTGRES_SYNC_URL về cùng DB đó; ARTIFACTS_DIR về thư mục tạm; DEBUG=false, MOCK_PROVIDERS=true, tắt tracing.
3. Chạy `alembic upgrade head`, sau đó `python -m pytest -q tests`; lưu exit code/summary. Dọn đúng DB đã tạo và artifacts tạm trong finally, không xóa volume dev.
4. Probe intake: tạo user/task tổng hợp qua ASGI, đặt task WAITING_USER_DATA trong DB test; gửi lần lượt payload metadata-only và payload thêm UUID file. Không bật lifespan/dispatcher. Mong đợi sau sửa: thiếu/sai file trả 4xx rõ ràng; file READY hợp lệ trả trạng thái queue thành công.
5. Probe FE: transpile api.ts bằng TypeScript, stub sessionStorage/fetch; so header của api.auth.me với api.tasks.list. Sau sửa, cả hai phải có Bearer khi có session.
6. Trong frontend chạy lint/build/audit; runtime chỉ đọc Compose config/ps, Alembic current, Redis PING/LLEN, Celery inspect ping và HTTP health/login.

Provider/browser E2E, restart/chaos, migration upgrade dữ liệu cũ, runner sandbox, security scan backend/container, load và backup/restore **chưa chạy trong audit này**. Các bước này đã vào P1–P10 và không được ghi thành pass trước khi có kết quả.

---

## Biên bản lịch sử — giữ nguyên mốc và giới hạn của từng lần

**Ngày kiểm tra:** 27/09/2026<br>
**Phạm vi:** Docker Compose, PostgreSQL/pgvector, Redis/Celery, FastAPI, Alembic, LangGraph compile và routing.<br>
**Môi trường:** Windows + Docker Desktop; backend image chạy Python 3.11.<br>
**Mục đích:** Xác nhận nền tảng kỹ thuật trước khi mở thêm tính năng. Đây là smoke verification, không phải nghiệm thu MVP hay production.

> **Ghi chú 08/10/2026:** Bảng dưới giữ nguyên evidence lịch sử. Lượt rà soát planning mới chỉ đọc source và sửa tài liệu; chưa chạy lại Docker/DB/provider. Migration head trong source nay khác baseline; không hiểu kết quả cũ là trạng thái DB hiện tại.

> **Lượt xác minh 18/10/2026 (Live Provider E2E Integration - Issue #2):** Đã kiểm chứng luồng end-to-end hoàn chỉnh trên live network với các provider thật: **Tavily Search API** (tìm kiếm và cào web song song), **Google Gemini Generative AI** (`gemini-3.5-flash-lite` cho Supervisor/Analyst/Critic và `gemini-3.5-flash` cho Writer), **Gemini Embeddings** (`models/gemini-embedding-2`, 3072 chiều) lưu trữ và truy vấn tương đồng ngữ nghĩa trên PostgreSQL pgvector. Pipeline đã hoàn thành chu trình đầy đủ (Supervisor → Researcher → Curator → Analyst → Writer → Critic → Revision → PostProcessor) cho bài nghiên cứu thực tế, tạo báo cáo hoàn chỉnh 1.325 từ với 9 trích dẫn khoa học được liên kết nguồn gốc đầy đủ.
>
> **Lượt xác minh trước đó (14/10/2026):** Xác minh lát cắt dọc bằng provider mocks (36/36 tests pass).

## Kết quả xác minh ngày 18/10/2026 — Live Provider E2E Research Workflow (Issue #2)

| Hạng mục | Kết quả thực tế | Giới hạn |
|---|---|---|
| Live Search & Fetch | Tavily API thực thi tìm kiếm song song theo 4 truy vấn sinh bởi Supervisor, cào nội dung web thực từ arXiv, LinearB, Funix. | Phụ thuộc kết nối mạng ngoài và quota gói phát triển của Tavily. |
| Ingestion & Embedding | Chia đoạn văn bản và tạo vector nhúng 3072 chiều với `models/gemini-embedding-2`, lưu trữ bền vững vào PostgreSQL pgvector; hỗ trợ cơ chế bọc retry và giới hạn mẻ tránh nghẽn RPM. | Tối đa 8 chunk giá trị cao cho mỗi nguồn để duy trì chi phí tối ưu. |
| Semantic Retrieval | Phân tích viên (Analyst) thực hiện truy vấn tương đồng cosine (`<=>`) trên pgvector để lấy các đoạn ngữ cảnh liên quan nhất cho từng truy vấn. | Ngưỡng khoảng cách cosine phụ thuộc vào chất lượng nội dung đoạn trích. |
| Claim & Evidence Lineage | Analyst trích xuất luận điểm với trích dẫn nguyên văn đối sánh chính xác với chunk nguồn; lưu trữ thành công các bản ghi `ResearchClaim`, `Evidence`, và bảng liên kết `ClaimEvidence` với `is_verified=True`. | Chỉ các luận điểm có bằng chứng khớp chính xác mới được đưa vào báo cáo. |
| Multi-Agent Writing & Criticism | Writer tạo bản thảo với các marker trích dẫn `[[@claim:...]]`; Critic (Devil's Advocate) duyệt với schema `CriticVerdict`, kích hoạt micro-loop điều chỉnh và Writer hoàn thiện bản thảo sửa đổi. | Bounded tối đa 2 lần sửa chữa nhỏ (micro revisions). |
| Citation Post-Processing | PostProcessor phân giải marker thành số trích dẫn chuẩn `[1]`...`[9]`, loại bỏ trích dẫn mô hình tự bịa và tổng hợp danh mục tài liệu tham khảo có URL nguồn gốc. | Chỉ trích dẫn các nguồn đã qua xác thực chuỗi chứng cứ. |
| Task Persistence & Report | Task `ec0de102-517f-4706-ae51-d46d21e7987e` đạt trạng thái `COMPLETED` tại bước `POST_PROCESSOR`, lưu `ResearchReport` dài 1.325 từ và 9 bản ghi `Citation` có thể truy cập qua API và giao diện UI. | Không có false completed; trạng thái hoàn thành phản ánh chính xác kết quả thực thi. |
| Vòng đời Cancel & Re-run | Endpoint `POST /{id}/cancel` hủy task an toàn, giải phóng khóa outbox; `POST /{id}/start` hỗ trợ chạy lại từ trạng thái CANCELLED với outbox redelivery. | Đã kiểm thử qua test suite và thực tế. |

## Kết quả xác minh ngày 14/10/2026 — Research Workflow Vertical Slice (Issue #2)

| Hạng mục | Kết quả thực tế | Giới hạn |
|---|---|---|
| Backend syntax | `python -m compileall -q backend/app backend/alembic` đạt 100%. | Không thay thế test tích hợp. |
| Backend test suite | `pytest -q tests`: **36 passed**, 3 deprecation warnings trong 12.97s. | Toàn bộ boundary nhà cung cấp ngoài (LLM, Tavily, Embedding) được giả lập để đảm bảo tính tất định và không phụ thuộc mạng ngoài. |
| Graph orchestration & routing | 27 bài test kiểm tra routing thẳng (Supervisor → Researcher → Curator → Analyst → Writer → Critic → PostProcessor), micro-loop (REVISE), macro-loop (NEED_MORE_DATA), cạn budget, và pipeline real-node. | Kiểm thử với provider boundary mocks; chưa kích hoạt model bên ngoài trên live network. |
| Lineage & Trích dẫn | Liên kết đầy đủ giữa Source, DocumentChunk, Evidence, ResearchClaim, ClaimEvidence, Citation và ResearchReport được ghi nhận bền vững vào PostgreSQL; endpoint `/citations` trả dữ liệu đã xác thực. | Kiểm tra tính toàn vẹn tham chiếu chuỗi chứng cứ; chưa đánh giá độ chính xác ngữ nghĩa bằng human review. |
| SSRF Guard | Đạt 10/10 test SSRF: chặn dải IPv4 non-public, loopback, IPv6 literal `[::1]`, IPv4-mapped loopback/private (`::ffff:`), IPv6 link-local (`fe80::`), unique-local (`fd00::`), non-HTTP scheme, và chặn follow redirect. | Áp dụng cho scraper HTTP client; không áp dụng cho các cuộc gọi nội bộ giữa API và Redis/DB. |
| Quota & Job limits | Đạt toàn bộ test tranh chấp claim giữa các worker, tối đa 2 RUNNING jobs/user, phục hồi worker hết hạn lease, và outbox dispatch retry khi broker gặp sự cố. | Giới hạn đo trên mức user và worker container đơn. |
| Frontend | `npm run lint` và `npm run build` hoàn thành với Next.js 15.5.27; workspace hiển thị tiến trình agent (`current_step`), báo cáo kết quả và tab trích dẫn có trích đoạn nguồn. | Sử dụng polling API (`GET /api/v1/research/{id}`) có kiểm soát; real-time SSE stream tạm thời tắt để tránh giả lập tiến độ. |
| Docker Compose | `docker compose config --quiet` đạt; PostgreSQL 16 + pgvector, Redis 7, backend và worker hoạt động đồng bộ. | Chưa đo benchmark tải cao nhiều người dùng đồng thời. |

Các lệnh xác minh đã chạy:

```powershell
docker compose config --quiet
docker compose exec -T backend python -m compileall -q app alembic
docker compose exec -T backend python -m pytest -q tests
cd frontend; npm run lint; npm run build
```

**Known Limitations & Tiêu chí còn lại của Issue #2:**
1. Luồng end-to-end với provider thật (Tavily search và LLM trả phí) chưa được kiểm thử trong CI tự động do giới hạn quota/credentials bên thứ ba; do đó Issue #2 tiếp tục duy trì trạng thái **Open** cho đến khi có lượt chạy kiểm chứng bằng tài khoản provider thật.
2. SSE streaming sự kiện thời gian thực hiện bị tắt, thay thế bằng cơ chế polling trạng thái chính xác theo đúng khuyến nghị của Issue #2.

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

## Kiểm tra 27/10/2026 — sửa bài kẹt QUEUED/RUNNING (#59)

Đây là bằng chứng mới hơn các mốc lịch sử ở trên, kiểm tra trên nhánh `bugfix/59-research-runtime-recovery`.

| Vấn đề | Nguyên nhân đã xác nhận | Cách xử lý |
|---|---|---|
| Worker lặp khôi phục, bài không tiến triển | Image worker cũ thiếu Postgres checkpointer; restart không cập nhật thư viện | API/worker cùng build; kiểm tra dependency trước khi nhận việc |
| Các job sau lỗi database | `asyncio.run()` tạo vòng sự kiện khác, dùng lại connection pool của vòng đã đóng | Một `asyncio.Runner` cho mỗi Celery child; đóng pool trên chính vòng đó |
| Đã claim nhưng bootstrap lỗi | Checkpoint/preload nằm ngoài handler của graph | Handler ngoài cùng cập nhật FAILED và giải phóng lease, có kiểm tra attempt để không ghi đè lần chạy mới |
| Không tải được nguồn HTTPS | TLS SNI nhận bytes thay vì chuỗi; mọi trang lỗi trước khi trích xuất | SNI dạng chuỗi đã thử với web thật; redirect được kiểm tra SSRF và ghim IP từng chặng; PDF công khai dùng parser PDF có giới hạn |
| Lựa chọn cấu hình bị bỏ qua | Thiếu các trường trong graph state; độ dài/kiểu citation chưa được áp dụng | Truyền lại cấu hình khi resume; Writer nhận độ dài và hạn đầu ra; formatter dùng IEEE/APA/Harvard với metadata có thật |
| Bài ngắn bị cắt mà vẫn PASS | Hạn token gồm cả suy luận; Critic không biết cấu trúc đầy đủ | Gemini dùng thinking level thấp, tăng headroom; ghi finish reason; bản bị cắt không thể COMPLETED; Critic nhận outline/yêu cầu bài |
| Giao việc hoặc khôi phục lặp mãi | Thiếu kết thúc khi hết số lần redelivery/recovery | FAILED với DISPATCH_FAILED/RECOVERY_LIMIT; có deadline cho provider và graph |
| Chạy lại mất lịch sử hoặc tính cả thời gian chờ | Report identity tạo mới; active clock chưa đóng ở trạng thái kết thúc | Tái sử dụng report, thêm immutable version; đóng clock khi dừng; giữ ngân sách đã tiêu |

| Kiểm tra | Kết quả |
|---|---|
| Backend toàn bộ trên PostgreSQL mới `issue59_verified_test` | **267 passed**; không chạy test trên database phát triển |
| Hồi quy redelivery sau khi bổ sung kết thúc FAILED | **3 passed** |
| Ma trận cấu hình REVIEW với provider giả lập, graph thật và interrupt/resume | **108 tổ hợp đạt**: 3 độ sâu × 3 độ dài × 3 kiểu trích dẫn × 2 chế độ duyệt × 2 ngôn ngữ |
| Celery thật, nhiều lần truy vấn DB liên tiếp | 12 deliveries qua prefork pool trả kết quả; không có lỗi connection khác event loop. Probe dùng ID không tồn tại, không gọi provider |
| REVIEW DEEP / LONG / IEEE, provider thật | COMPLETED; 5 nguồn, 8 citation, phiên bản 2; phiên bản 1 thiếu nguồn được giữ nguyên |
| REVIEW SHALLOW / SHORT / APA / English / duyệt kế hoạch, provider thật | WAITING_APPROVAL → duyệt → COMPLETED; 569 từ, 7 citation |
| REVIEW STANDARD / MEDIUM / Harvard / Vietnamese, provider thật | Kết thúc NEEDS_REVIEW; 1.040 từ, 9 citation; cần xem góp ý nội dung, worker không còn chạy |
| Frontend | 14 tests đạt; production build/typecheck đạt |
| Docker và migration | Backend image build đạt; runtime preflight đạt; migration sạch tới `a6b7c8d9e0f1` và upgrade database dev đạt |

108 tổ hợp là kiểm thử điều phối với provider giả lập, không phải 108 lần gọi dịch vụ thật. Các đường empirical tiếp tục được kiểm thử integration với dữ liệu/routine có kiểm soát; đợt kiểm tra provider thật này tập trung REVIEW. PASS của Critic là kiểm soát chất lượng nội bộ, không phải xác nhận bài đủ điều kiện công bố. Kiểu APA/Harvard hiện dựa trên metadata web cơ bản; tác giả/ngày thiếu được giữ thiếu, không tự suy đoán.

Tài khoản và bài dùng riêng cho smoke test đã được dọn; dữ liệu nghiên cứu thật và các phiên bản cũ được giữ lại. Hướng dẫn rebuild và retry nằm trong README. Đợt sửa này không thay cho nghiệm thu tải, backup/restore và bảo mật production.
