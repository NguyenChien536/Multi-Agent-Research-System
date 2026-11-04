# Bản Docker dùng để demo cuối kỳ

## Cập nhật nghiệm thu candidate 04/11/2026

**Candidate hiện tại: `ad66fd5a4a71` trên nhánh `feature/89-workspace-ui-export-fidelity`.** CI của PR #107 pass đủ sáu job: branch policy, backend syntax/tests, frontend build, Compose build và release runtime. Đã build lại image và triển khai candidate này qua Docker Compose; API, frontend, worker, gateway, PostgreSQL và Redis đều healthy, readiness trả `ready`.

**Ghi chú build Windows:** `npm run build` cục bộ không hoàn tất do `frontend/.next/diagnostics/framework.json` là reparse point trong OneDrive và Next.js báo `EINVAL`. Production build/typecheck pass trong GitHub CI và Docker Linux; không xóa `.next` theo cách đệ quy khi chưa xác định đích của reparse point.

| Kiểm tra candidate hiện tại | Kết quả |
|---|---|
| Release runtime không gọi provider | Pass trong CI trên candidate này: gateway, readiness, đăng nhập, ownership, monitor và lỗi khi broker dừng |
| Dữ liệu sau restart/thay image | Pass: profile, ba bài, trạng thái, monitor và CSV tổng hợp 1.176 byte (SHA-256 khớp) còn nguyên sau restart và sau khi triển khai candidate này; không có bài RUNNING/QUEUED bị gián đoạn |
| API phiên bản khi chưa có bản thảo | Pass: test PostgreSQL cô lập 1/1; task của chủ sở hữu trả `200 []`, task của người khác vẫn trả `404` |
| Backup/restore | Pass trên candidate cũ `9a1617abee7b`: backup PostgreSQL + artifacts được khôi phục sang project riêng `synthia-restore-final-9a1617`; file/checksum khớp. Không chạy lại backup/restore sau candidate này |
| Giao diện đã đăng nhập | Workspace đã kiểm tra bằng tiếng Anh/Việt trên `bd5d60f`; trên candidate hiện tại, trang phiên bản hiển thị đúng trạng thái “chưa có bản thảo”, không hiện lỗi 404 giả và không cho gửi yêu cầu sửa khi chưa có bài |
| Nội dung bài/Word export | Test frontend pass trong CI; kiểm tra cấu trúc export bằng fixture xác nhận giữ nội dung và tài liệu tham khảo của phiên bản, không thêm DOI/tác giả/abstract/keywords bịa. Chưa kiểm tra file export từ bài thật vì release smoke chưa có bản thảo |
| Nghiên cứu với provider | **Chưa chạy trên candidate hiện tại.** Ba bài smoke ở trạng thái PENDING; không gọi model hay search API |

PR #107 vẫn là draft. `main` chưa thay đổi và chưa được promote. Các kết quả provider-backed ở những mục lịch sử bên dưới thuộc các candidate cũ; không được xem là bằng chứng chạy provider trên `ad66fd5a4a71`.

**Nghiệm thu local 03/11/2026:** hạ tầng, backup/restore và luồng nghiên cứu đã chạy thực tế. #93 và #95 đã sửa, kiểm thử và merge vào `develop`. Candidate `2bc6151573d8` đã qua đủ 6 kiểm tra CI và chạy với provider thật; mã runtime tương ứng được merge tại `ac4c886a3eec`. **Chưa đưa lên main hoặc chốt chất lượng bài nộp**: tiếp tục cải thiện độ phủ bằng chứng (#86) và đánh giá pilot (#83).

| Kiểm tra thực tế | Kết quả |
|---|---|
| Web/API cùng origin, login, owner isolation, monitor | Pass trên Docker local |
| Human-led với provider thật | Lưu protocol và dừng `WAITING_USER_DATA`; trả worker |
| Computational với CSV synthetic được gắn nhãn kiểm thử, 60 dòng | Routine hoàn tất; repeatability `PASSED`; 7 journal entries; có bản thảo `NEEDS_REVIEW` và gói tái lập ZIP tải được, kiểm tra archive hợp lệ |
| Gói tái lập gắn phiên bản | #95 giữ nguyên execution timestamp; regression tái hiện lỗi trước sửa và pass sau sửa. Luồng CSV thật trên candidate mới đã xuất được bundle |
| REVIEW với provider thật | Báo cáo 1.819 từ mở được và xuất được hai ZIP nguồn IEEE/ACM; trạng thái `NEEDS_REVIEW`, budget-limited. Đây là runtime pass, chưa phải scientific-quality pass; bibliography mới có một nguồn |
| Giữ bản nháp khi provider từ chối do hạn mức | #93 lấy đúng checkpoint của task/run/attempt rồi chỉ định dạng bằng code. 158 test liên quan pass; test API→worker tái hiện đúng nhánh budget exception, cancellation và duplicate delivery. Lần REVIEW thật mới hoàn tất qua nhánh Critic budget-limited, không dùng riêng nhánh phục hồi checkpoint; hai loại bằng chứng kiểm thử được phân biệt |
| Backup và restore sang project riêng | Kiểm tra trên candidate trước (`1a84aeb84c30`): đăng nhập lại, phục hồi 3 bài; manuscript khớp nguyên bản, artifact tải xuống có cùng SHA-256; project phục hồi đã dừng. Không có migration thay đổi cấu trúc dữ liệu trong #93/#95 |

## 1. Phạm vi và cách chạy

Bản release chạy trên **máy hiện tại**, truy cập tại **http://127.0.0.1:3080**. Đây là cấu hình triển khai local: không bật reload, không mount mã nguồn, không mở cổng PostgreSQL/Redis ra máy chủ. Bản này có database, Redis và kho file riêng với môi trường phát triển ở cổng 3000/8000; các bài cũ ở môi trường phát triển không tự xuất hiện trong release.

Mở PowerShell tại thư mục gốc dự án, bật Docker Desktop rồi chạy:

```powershell
# Chỉ chạy một lần; tạo secret riêng và sao chép cấu hình provider từ .env trên máy.
.\scripts\release.ps1 -Action init

# Build, migration, đợi các service healthy.
.\scripts\release.ps1 -Action start
.\scripts\release.ps1 -Action status

# Dừng và giữ toàn bộ dữ liệu.
.\scripts\release.ps1 -Action stop
```

Không đưa `scratch/release-local/.env`, tài khoản demo, bản thảo riêng hoặc bản backup lên GitHub. `init` không thay secret đã có; thay secret sau khi đã dùng sẽ làm phiên đăng nhập cũ hết hiệu lực. Provider vẫn cần Internet và quota/API key hợp lệ; Docker không thay thế nhà cung cấp mô hình/tìm kiếm.

## 2. Kiến trúc thực sự chạy trong bản release

```mermaid
flowchart LR
    U([Trình duyệt]) -->|HTTP: loopback 3080| N[Nginx gateway]
    N -->|Trang và assets| F[Next.js standalone]
    N -->|REST /api/v1| A[FastAPI + outbox dispatcher]
    A -->|Task, ownership, outbox| P[(PostgreSQL + pgvector)]
    A -->|Publish job| R[(Redis)]
    R -->|Deliver job| W[Celery worker]
    W --> G[LangGraph: agent workflow]
    G -->|State, checkpoint, report, journal| P
    G -->|Search / LLM / embedding| X[Provider ngoài hệ thống]
    G -->|Routine cố định khi có CSV| E[Process phân tích có giới hạn]
    E --> S[(Private artifact volume)]
    G --> S
    A -->|Download sau kiểm tra owner| S
    F -.->|Polling monitor qua gateway| A
```

Đây là **modular monolith** với API và worker triển khai thành hai tiến trình từ cùng một backend image. Mỗi agent là một vai trò trong graph, không phải một microservice. LangGraph là thư viện chạy trong worker. PostgreSQL giữ trạng thái bền vững; Redis chuyển job và có thể giao lặp, nên worker dùng claim/lease và kiểm phiên bản. Transactional outbox tránh mất yêu cầu giữa bước ghi database và gửi broker; không hứa exactly-once cho lời gọi provider.

Monitor hiện dùng **polling endpoint đã xác thực** để đọc snapshot, agent runs, thời gian, token/chi phí và lỗi. Cấu hình gateway không buffer luồng API để có thể hỗ trợ streaming; điều đó không có nghĩa bản hiện tại đã triển khai SSE replay.

`WAITING_USER_DATA`/chờ duyệt được lưu bằng checkpoint; worker kết thúc job và trả tài nguyên. Người dùng có thể mở nhiều bài khác trong khi chờ. Mỗi bài chỉ có một active run; quota giới hạn số bài chạy đồng thời. Upload/resume phải khớp owner, plan và checkpoint.

## 3. Chức năng, công nghệ và giới hạn để giải thích khi demo

| Nội dung | Cách thực hiện | Giới hạn phải nói rõ |
|---|---|---|
| Tổng quan tài liệu | Search + thu thập/parse + retrieval + Evidence Analyst + Writer/Critic + citation validation | Không bảo đảm tìm hết tài liệu hoặc trở thành systematic review chỉ nhờ tên mục |
| Tìm nguồn học thuật | Tavily, OpenAlex/Crossref và URL truy cập được | Một landing page/abstract không tương đương toàn văn; có thể bị rate limit/paywall |
| Thực nghiệm tính toán | Upload CSV numeric, routine `tabular_regression_v1`, baseline/Ridge, metric/figure, journal và gói tái lập | Chỉ routine được hỗ trợ; chưa chạy tùy ý code do LLM sinh. Process bị giới hạn không được giới thiệu là sandbox cho mã không tin cậy |
| Nghiên cứu ngoài hệ thống | Sinh protocol, dừng chờ, nạp kết quả có provenance rồi tiếp tục viết | Người nghiên cứu chịu trách nhiệm thu thập, đồng thuận/phê duyệt nếu cần; hệ thống không tự nhận đã làm khảo sát/lab |
| Bản thảo và xuất bài | Markdown, Word, in PDF bằng trình duyệt; ZIP nguồn LaTeX IEEE/ACM gắn report version | ZIP là nguồn cần người dùng kiểm tra/biên dịch; Word hiện không nhúng mọi figure. Không tự tạo tác giả, DOI hoặc trạng thái xuất bản |
| Theo dõi và truy nguyên | Monitor, agent runs, version báo cáo, citation/evidence lineage, experiment journal | Lineage đúng không tự chứng minh nội dung khoa học đúng; Critic không phải peer review độc lập |

Thiết kế dùng các module riêng cho budget/provider, evidence, manuscript, export và storage. API kiểm quyền sở hữu trước khi truy cập tài nguyên; bản download không mở trực tiếp thư mục artifact qua gateway. Dependency Python/Node được khóa; image ứng dụng chạy non-root, filesystem chỉ đọc, chỉ volume artifact và `/tmp` được ghi. Migration chạy thành job riêng trước API/worker.

## 4. Kiểm tra và phân biệt hai loại kết quả

```powershell
# Không gọi provider, kiểm tra web/API, login, ownership, tạo 3 loại bài và monitor.
.\.venv\Scripts\python.exe scripts/release-smoke.py

# Có gọi provider thật: chỉ một bài, cap 0.50 USD, 25 LLM calls, timeout 900 giây.
.\.venv\Scripts\python.exe scripts/release-smoke.py --generate REVIEW --output scratch/release-local/review
```

Lệnh Python dùng thư viện chuẩn; có thể dùng Python 3.11+ thay đường dẫn `.venv`. Các file kết quả/tài khoản nằm trong thư mục output riêng tư. Không chạy lại chiến dịch provider nhiều lần chỉ để tìm ra một kết quả đẹp.

**Runtime pass:** job được nhận, thực thi, lưu output/checkpoint đúng, monitor và export truy cập được. **Scientific quality:** đánh giá bố cục, nguồn, mức hỗ trợ của luận điểm, phương pháp và kết quả thực. `PARTIAL`/`NEEDS_REVIEW` là kết quả cần sửa, không được đổi tên thành bài hoàn tất chỉ để demo. Bản thảo `COMPLETED` vẫn cần người nghiên cứu kiểm chứng trước sử dụng học thuật.

CI kiểm backend, frontend, quy tắc nhánh và build dev; job `Release runtime` còn dựng release từ database sạch, chạy smoke không tốn provider và thử broker mất/kết nối lại. Real-provider/browser và backup/restore là các gate local riêng, không được suy ra từ test mock.

### Kết quả kiểm tra nguồn ngày 03/11/2026

| Candidate / kiểm tra | Kết quả thực tế | Kết luận được phép |
|---|---|---|
| `e78125125154`, REVIEW cũ | Lần đầu provider 503; retry sinh bản thảo 1.673 từ, 2 citation records cùng một nguồn | Giữ cả lỗi và kết quả yếu; chưa đạt chất lượng nguồn |
| `d235b3a31cda`, REVIEW mới, cap 6 nguồn / 0,50 USD | 6 nguồn thu thập (4 toàn văn, 2 abstract), 6 quote-linked claim candidates; bản thảo 2.095 từ, 4 citation records trỏ 3 nguồn khác nhau; có mục con, gói IEEE/ACM ZIP hợp lệ; 6/6 CI đạt với 562 backend tests | Runtime chạy được; đây là chẩn đoán một bài, không phải thử nghiệm A/B hoặc bằng chứng chất lượng tăng trên mọi chủ đề |
| Audit nội dung của bài trên | Một nhu cầu bằng chứng trung tâm chưa có quote; còn phát biểu quá rộng về peer-review, lịch sử, định nghĩa và so sánh baseline. Critic nội bộ đã đánh giá nhiều đoạn quá lạc quan dù gate cuối vẫn NEEDS_REVIEW | Không coi bài là đủ chuẩn nộp/xuất bản. #86 và đánh giá #83 còn mở; chưa đưa lên main |

Sau audit này, context của Critic được bổ sung ma trận thiếu bằng chứng, giả định và yêu cầu đánh giá quote thay vì tin diễn giải claim do AI sinh. Bằng chứng provider trong bảng thuộc đúng SHA đã ghi, **không tự áp dụng cho revision mới**. Kiểm thử tự động xác minh cách truyền context và giữ gate; hiệu quả phát hiện sai khoa học cần được chấm tiếp. Không tự sửa bài lịch sử hoặc nâng trạng thái để làm đẹp demo.

### Kiểm tra tiếp theo: phân bổ nguồn và quote anchor (#101)

Candidate `4fc6ddb2887e` đạt 6/6 CI, gồm 582 backend tests; build release và smoke HTTP không gọi provider đều đạt. Lượt hiệu chỉnh riêng dùng đúng Critic và model đang cấu hình, có giới hạn gọi/chi phí và không ghi vào bài cũ: hai đoạn từng bị duyệt sai được đánh giá PARTIAL, chỉ rõ phần lịch sử/diễn giải không có nguồn; đoạn đối chứng trích nguyên văn được đánh giá SUPPORTED. Đã thực hiện hai lời gọi provider. Một lần chuẩn bị trước đó thiếu trường cấu hình của script, dừng trước provider; log và reservation vẫn được giữ. Đây là ca đã biết, không phải tập held-out, không chứng minh độ chính xác tổng quát; provider cũng báo bỏ qua cấu hình temperature, nên không coi đây là thử nghiệm kiểm soát sampling.

Trên cùng candidate, nhánh tính toán với dữ liệu **tổng hợp để kiểm tra phần mềm** đã đi qua WAITING_USER_DATA → upload 60 dòng → chạy `tabular_regression_v1` → lưu bài và experiment ZIP. Analysis COMPLETED, kiểm tra lặp lại PASSED, 7 journal entries; MAE baseline = 3,849167 và Ridge = 0,087204 trên 12 dòng test của một split. ZIP có dữ liệu, routine, config, metrics, figures, journal và manifest, kiểm tra archive đạt. Chỉ kết luận về lần chạy này, không suy hiệu quả nghiên cứu trên dữ liệu thật.

Bài tính toán 1.475 từ vẫn NEEDS_REVIEW, chưa có citation nền tảng được giữ. Nhật ký cho thấy một số câu hỏi tìm nguồn đang lẫn với bằng chứng cần lấy từ thực nghiệm. Chỉ dẫn lập kế hoạch được làm rõ: truy vấn tài liệu phục vụ prior work/định nghĩa/phương pháp; kết quả trên dataset hiện tại phải lấy từ analysis hoặc dữ liệu người dùng. FOUNDATION dành cho công trình gốc, không gán cho câu hỏi về tài liệu hướng dẫn thư viện. Chưa coi sửa chỉ dẫn là bằng chứng mọi chủ đề đã được giải quyết; #86/#83 còn mở, chưa promote main.

## 5. Theo dõi lỗi, sao lưu và khôi phục

```powershell
.\scripts\release.ps1 -Action logs
.\scripts\release.ps1 -Action backup

# Dùng đường dẫn backup vừa tạo; chỉ cho phép khôi phục sang project MỚI.
.\scripts\release.ps1 -Action restore -Project synthia-restore-check -Port 3081 -BackupPath '<duong-dan-backup>'
.\scripts\release.ps1 -Action status -Project synthia-restore-check -Port 3081
.\scripts\release.ps1 -Action stop -Project synthia-restore-check -Port 3081
```

Backup tạm dừng API ingress, từ chối nếu có bài QUEUED/RUNNING rồi dừng worker, lưu PostgreSQL và artifact cùng manifest/checksum. Redis không phải bản sao trạng thái nghiên cứu; bản restore chỉ dành cho snapshot không có job đang chạy. Script không xóa volume và không cho restore đè project demo chính. Kiểm tra dữ liệu/bản thảo/download trên project phục hồi trước khi coi backup là đã nghiệm thu.

Khi gặp lỗi, lưu task ID, thời gian, revision và monitor; xem log backend/worker. Không sửa database để ép trạng thái COMPLETED. Khi provider hết quota, sửa cấu hình provider rồi thực hiện retry có chủ đích; giữ bản ghi lỗi/kết quả âm. Không chia sẻ log chứa nội dung nghiên cứu riêng tư.

## 6. Gate trước khi đưa bản candidate lên main

1. CI của đúng revision pass, build image release thành công.
2. Fresh install, readiness và worker health pass; kiểm tra host chỉ mở cổng release trên loopback.
3. Luồng thực với provider và giao diện hoạt động; nội dung/kết quả chưa đạt phải ghi rõ, không che trạng thái.
4. Các nhánh review, computational và human-led có bằng chứng chạy hoặc checkpoint phù hợp; download theo đúng phiên bản và owner.
5. Restart giữ tài khoản/bài/file; backup/restore được thử trên project riêng.
6. Review diff và rủi ro còn lại; chỉ merge `develop → main` sau các gate trên. Chưa có đánh giá đủ mạnh thì không tuyên bố multi-agent tốt hơn baseline hay đủ an toàn để mở public Internet.
