# SRS — Multi-Agent Research System (ATI)

> **Phiên bản:** 4.1 · **Cập nhật định hướng:** 09/10/2026 · **Kỳ hạn:** 10/09–10/11/2026.
> Yêu cầu mục tiêu, không phải danh sách tính năng đã nghiệm thu. Thay v3.0; `SRS ATI.md` v2.5 là bản lịch sử. Sơ đồ chuẩn: [System Design](../architecture/system-design.md). Review: [Product Assessment](../project/product-assessment.md).

## 1. Mục đích và giá trị

ATI là hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập: nhận câu hỏi/nguồn riêng, lập kế hoạch, tìm/đối chiếu tài liệu, gợi ý khoảng trống nghiên cứu/giả thuyết, chọn phương pháp, thực hiện phân tích được hỗ trợ và tạo **bản thảo bài báo hoàn chỉnh theo loại nghiên cứu**. Người dùng hỏi tiếp và sửa bài trong cùng task. “Hoàn chỉnh” nghĩa là đủ các phần và có dữ liệu/bằng chứng thật cần cho loại bài; không có nghĩa đã được bình duyệt hoặc bảo đảm được công bố.

Giá trị cần đánh giá là chất lượng evidence/report và hiệu quả vòng phản biện so với single-agent dùng cùng nguồn, model và giới hạn tài nguyên. Số agent không phải thước đo chất lượng.

## 2. Người dùng, phạm vi và đầu ra

Người dùng chính là sinh viên/nhà nghiên cứu cá nhân; mỗi tài khoản có nhiều task/bài nghiên cứu độc lập. Bản nộp chưa có workspace chia sẻ hoặc tenant doanh nghiệp. Nguyễn Đình Chiến phụ trách thiết kế, triển khai và xác minh kỹ thuật.

| Loại đầu ra | Cấu trúc tối thiểu | Điều kiện |
|---|---|---|
| `REVIEW` — tổng quan tài liệu | Title, Abstract, Introduction, phạm vi/cách tìm nguồn, tổng hợp theo chủ đề, Discussion/gợi ý khoảng trống, Limitations, Conclusion, References | Ghi corpus, ngày tìm, loại nguồn và giới hạn; không tự gắn nhãn systematic review/PRISMA |
| `EMPIRICAL_COMPUTATIONAL` — bài thực nghiệm tính toán | Title, Abstract, Introduction/Related work, Research question/hypothesis, Methods, Results, Discussion, Limitations, Conclusion, References, reproducibility appendix | Routine được hỗ trợ chạy thật thành công, metrics/charts/manifest đã kiểm tra |
| `EMPIRICAL_HUMAN` — bài thực nghiệm với lab/khảo sát/thực địa | Title, Abstract, Introduction/Related work, Research question/hypothesis, Methods, Results, Discussion, Limitations, Conclusion, References và provenance dữ liệu/kết quả | Chỉ hoàn thành sau khi người dùng cung cấp kết quả thực và thông tin phương pháp đủ kiểm; nêu rõ phần ATI phân tích lại và phần chỉ dựa vào báo cáo của người dùng |

Đầu ra chính ở trạng thái `COMPLETED` là **bài báo Markdown đầy đủ**, kèm tóm tắt dễ đọc, citations/nguồn có thể kiểm, trạng thái kiểm tra và các phụ lục phù hợp. Bài tính toán có thêm bảng/biểu đồ và gói tái lập; bài human-led có provenance dữ liệu/kết quả và giới hạn xác minh. Protocol đã phản biện, biểu mẫu thu thập, bản nháp chưa có Results và nguồn đang thu thập là **artifacts trung gian**, có thể tải về nhưng không được hiển thị là bài báo đã hoàn thành. PDF/DOCX đẹp, OCR, SPSS, video, mọi journal template, dữ liệu nhạy cảm, GPU training và arbitrary-code execution ngoài bản nộp.

Review và human-led protocol nhận câu hỏi nhiều lĩnh vực; thực thi tự động ban đầu chỉ gồm **CSV numeric → thống kê mô tả → so sánh dự đoán biến số bằng baseline và Ridge**. Không suy ra nhân quả hoặc cam kết novelty. Lab/khảo sát/thực địa do con người thực hiện ngoài ATI. Nếu không có dữ liệu/kết quả thật hoặc thông tin phương pháp tối thiểu, bài human-led tiếp tục chờ; không sinh Results từ giả định. Protocol paper độc lập chỉ là output khác nếu người dùng yêu cầu rõ và được thiết kế riêng sau bản nộp.

## 3. Chức năng và nghiệm thu

`Core` bắt buộc trước 10/11; `Later` sau bản nộp.

| ID | Yêu cầu | Tiêu chí nghiệm thu | Mức |
|---|---|---|---|
| FR-01 | Tài khoản/task ownership | Login/session; task/source/report/artifact/event chỉ owner truy cập; hai user không đọc/sửa dữ liệu nhau | Core |
| FR-02 | Web và PDF | PDF có text; size/type/owner/checksum hợp lệ; ingest async, lỗi có lý do; chỉ nguồn READY tạo evidence | Core |
| FR-03 | Plan và quyền tự xử lý | Plan version ghi câu hỏi con, scope, output, tools, budget; assisted có approve/revise/cancel; automatic ghi quyết định theo policy đã cấp | Core |
| FR-04 | Evidence/gợi ý khoảng trống | Claim liên kết chunk/source; quote/locator, counterevidence và search limits; UI dùng “Gợi ý khoảng trống nghiên cứu”, không khẳng định novelty tuyệt đối | Core |
| FR-05 | Research loop | Tối đa 3 vòng thu thập gồm vòng đầu; targeted query từ thiếu sót cụ thể; dừng nếu không thêm evidence dùng được sau dedup/hết budget | Core |
| FR-06 | Phương pháp/protocol | Câu hỏi/giả thuyết khi phù hợp, biến số, phương pháp, data cần, metric; protocol cũng qua Writer/Critic/Validator | Core |
| FR-07 | Thí nghiệm thật | Routine allowlist ngoài API/worker; CSV hợp lệ; baseline + Ridge cùng split/metric; lưu input hash/config/seed/code/version/metrics/charts/errors | Core |
| FR-08 | Chờ data/resume | WAITING_USER_DATA có checkpoint, worker kết thúc; protocol là artifact trung gian; upload READY + quyết định hợp lệ resume đúng checkpoint; input chưa đủ tiếp tục chờ hoặc yêu cầu sửa | Core |
| FR-09 | Bài báo theo loại | `COMPLETED` có toàn bộ phần mục 2 và Results thật khi bắt buộc; thiếu data chỉ trả protocol/bản nháp đúng nhãn, không tự đổi loại bài rồi báo hoàn thành | Core |
| FR-10 | Critic/sửa | Review theo section cùng evidence/method/results; tối đa 2 lần sửa sau draft đầu; verdict có issue IDs và claim/section liên quan | Core |
| FR-11 | Citation/provenance | Citation thư mục → source/chunk; claim kết quả → evidence → output artifact → run/input/config; kiểm cùng task và toàn bài | Core |
| FR-12 | Agent progress/monitoring | UI role/stage/status/iteration/budget/warning; DB event timeline, polling fallback; structured logs có task/run/step IDs, latency/usage/redaction | Core |
| FR-13 | Export | Markdown/report versions; input được phép, config, routine source hoặc launcher, metrics JSON/CSV, chart PNG, manifest/README tái lập; owner-only download | Core |
| FR-14 | Ảnh tùy chọn | Ưu tiên ảnh source, Serper backend tùy chọn; attribution/license; tự bỏ qua khi thiếu, user bỏ ảnh/tắt tất cả; ảnh minh họa không là evidence | Later |
| FR-15 | Q&A/sửa bản thảo | Q&A theo report version + evidence, có citations; chỉnh bài tạo version mới; đổi data/method có plan/run revision và trace | Core |
| FR-16 | Đánh giá multi-agent | Query/corpus/rubric versioned; baseline/ablation; cấu hình, cost, kết quả/người chấm; báo cáo cả thất bại/giới hạn | Core |
| FR-17 | Nhiều bài độc lập | Một user tạo/xem/chuyển giữa nhiều task; task A chờ dữ liệu không cản tạo/chạy task B; danh sách hiển thị status/stage/việc cần làm và bản thảo mới nhất | Core |

FR-07 và FR-08 là hai nhánh của plan: ATI chạy routine hỗ trợ, hoặc hướng dẫn nghiên cứu viên thực hiện ngoài hệ thống và nhận data/results có provenance. User-supplied results luôn có nhãn, không được báo đã tái lập nếu ATI chưa chạy lại.

## 4. Tương tác và quyền hạn

- Form chỉ bắt buộc câu hỏi; sources/data tùy chọn. ATI đề xuất loại bài và method; user được đổi trước thực thi. Dashboard liệt kê từng bài với trạng thái, bước hiện tại, việc cần làm, thời điểm cập nhật và link mở đúng workspace.
- `ASSISTED` yêu cầu duyệt plan. `AUTOMATIC` tiếp tục bước trong quyền/cap đã cấp, ghi audit; user vẫn xem/hủy được.
- Không tự vượt budget, đổi sang provider không được phép nhận data, duyệt ethics, tuyển người hoặc suy ra dữ liệu chưa có.
- Q&A chỉ đọc, không chạy lại toàn research. Revision có job/version riêng; yêu cầu xung đột khi task đang chạy trả lỗi rõ.
- Q&A gắn `operation_id` và `report_version`, dùng cùng budget adapter với cap riêng do server cấu hình và quota của task; không mở lại hoặc reset budget của research run đã kết thúc. Chưa cấp budget thì không gọi provider tốn phí.
- UI hiển thị bước và output quan sát được; không công khai chain-of-thought, secrets hay raw private prompts.

## 5. Lifecycle

ResearchTask là workspace dài hạn. ResearchRun là lần chạy/revision; tối đa một active run/task. `status` là lifecycle; `stage` là PLANNING/SEARCHING/INGESTING/ANALYZING/EXPERIMENTING/WRITING/REVIEWING/VALIDATING. Không dùng stage thay lifecycle.

Một user sở hữu nhiều `ResearchTask`. Mỗi task có plan, corpus, file, checkpoint, event timeline, run và report versions riêng. `WAITING_USER_DATA` của task A không chiếm worker hoặc suất chạy đồng thời; user có thể làm task B. Mặc định tối đa **2 job RUNNING mỗi user** (cấu hình server, phải thực thi bằng claim/lease ở dispatcher/worker), không giới hạn số task chờ theo mức này; quota số task/tổng lưu trữ được cấu hình riêng. Khi resume A mà cả hai suất bận, A vào QUEUED/outbox bền vững và được dispatch khi có suất, không đánh mất upload/decision. Một task vẫn chỉ có một run chưa terminal tại một thời điểm.

| Status | Ý nghĩa |
|---|---|
| PENDING | Đã tạo task, chưa có job |
| QUEUED / RUNNING | Job chờ/chạy |
| WAITING_APPROVAL / WAITING_USER_DATA | Checkpoint lưu bền vững, worker kết thúc; cần input có quyền |
| COMPLETED | Bài báo đúng loại có đủ phần và evidence/results bắt buộc, technical gates đạt; không đồng nghĩa được xác nhận khoa học |
| PARTIAL | Draft có tham chiếu hợp lệ nhưng thiếu nội dung/evidence, phần thiếu được công khai |
| NEEDS_REVIEW | Lỗi reference/method/result chưa giải quyết; không xuất như bài đã kiểm tra |
| FAILED / CANCELLED | Lỗi không có output dùng được / user hủy |

Resume giữ run ID; revision sau terminal tạo run mới. QUEUED, RUNNING và WAITING_* đều chiếm vị trí active run **của chính task đó**; WAITING_* không chiếm quota job RUNNING của user và không giữ worker lease. Khi đang chờ, chỉ duyệt/sửa plan hoặc resume đúng version; muốn bắt đầu research revision khác trên cùng task phải hủy run hiện tại trước. Checkpoint/version/decision ID phải khớp; delivery lặp không tạo output trùng. Active-time budget không tính ngày chờ user. Dữ liệu tới muộn phải so với plan/method version: khác phiên bản thì không dùng lại Results cũ. Hủy/xóa task A không tác động task B.

## 6. Giới hạn ban đầu

Đây là **default thiết kế cần xác minh**, không phải số đo đạt được. Server giữ cap; user không tăng vượt project cap.

| Tài nguyên | Default bản nộp |
|---|---|
| Research / writer loops | 3 tổng vòng thu thập / 2 lần sửa sau draft đầu; citation repair dùng chung revision counter |
| Sources / search concurrency | 12 nguồn mặc định, trần 20 / 2 truy vấn đồng thời |
| LLM / provider budget | Tối đa 40 LLM calls/run, kể cả retry/fallback; tổng chi phí provider ước tính ≤2 USD/run gồm LLM, embedding và search; cần price table hợp lệ |
| Active runtime | 15 phút/run, không tính WAITING_* |
| PDF | 5 file/task, 10 MiB và 100 trang/file; không OCR |
| CSV | 5 MiB, 20.000 hàng, 30 cột số; target số, không định danh |
| Runner | 1 job, 2 CPU/1 GiB RAM/120 giây; input read-only, output ≤20 MiB, no network |
| Retry | Tối đa 2 retry lỗi tạm thời; reserve mỗi attempt; analysis retry giữ config/seed |
| Đồng thời theo user | Tối đa 2 job RUNNING; QUEUED/WAITING_* không chiếm suất; quota task/storage độc lập |

Budget manager reserve worst-case theo max tokens/quota trước call, reconcile usage sau. Giá/usage không xác định thì chặn paid call hoặc dùng quota cứng đã cấu hình; estimate không cam kết hóa đơn chính xác. Timeout không thu hồi được request provider đã nhận.

## 7. Chất lượng và dữ liệu

- Ownership trên API/SQL/storage; cache/log không trộn user/task; không nhận dữ liệu định danh nhạy cảm trong bản nộp.
- Fetch kiểm scheme/DNS/redirect tại kết nối thực, giới hạn bytes/time/type. Upload kiểm extension/MIME/signature, parser timeout và malformed input.
- Web/PDF là dữ liệu không tin cậy, không được điều khiển tools qua chỉ dẫn trong nguồn. Sanitize Markdown/HTML.
- Runner chỉ nhận routine ID/config/artifact IDs; không nhận code/shell từ LLM. Docker restricted runner là môi trường demo kiểm soát, không là sandbox cho mã thù địch.
- Private files: owner xóa task → tombstone và thu hồi quyền đọc/ghi/resume ngay; yêu cầu cancel được worker/launcher xử lý tại safe boundary. Provider request đã gửi có thể vẫn kết thúc nhưng không được phát hành kết quả hoặc ghi lại vào task đã xóa. Purge file/index/checkpoint/cache/event trong 24 giờ; cleanup retry khi lỗi. Không TTL xóa ngầm trước khi user tải output. Backup demo purge tối đa 7 ngày; cấu hình/thông báo trước khi dùng dữ liệu thật, không hứa xóa bản sao phía provider ngoài chính sách của họ.
- Pin provider/model/embedding profile theo run/corpus; fallback theo allowlist/data policy; đổi embedding phải re-index.
- DB là nguồn sự thật; SSE/polling phản ánh DB. Log IDs, role/provider/usage/latency/error code; không ghi secrets/raw private content.

Các NFR dưới đây định danh những ràng buộc đã nêu ở mục 4–7 để theo dõi triển khai; không tạo thêm phạm vi sản phẩm.

| ID | Nhóm yêu cầu phi chức năng | Nghiệm thu chính |
|---|---|---|
| NFR-01 | Quyền truy cập và riêng tư | Owner isolation trên API, retrieval, artifacts, events, cache; secrets/private content không lộ qua log |
| NFR-02 | Tính bền vững và idempotency | Broker lỗi, job lặp, restart, stale decision/cancel không mất hoặc nhân đôi output |
| NFR-03 | Budget và giới hạn | Reserve trước mọi call/retry; caps mục 6; no-delta và hết budget dừng đúng trạng thái |
| NFR-04 | Input và execution boundary | Fetch/upload có giới hạn; nguồn không điều khiển tools; runner chỉ routine cho phép |
| NFR-05 | Khả năng tái lập | Pin dependencies/model/embedding profile; manifest input/config/seed; không dùng lại result sai phiên bản |
| NFR-06 | Khả năng quan sát | State/stage/event/log có IDs và usage; UI reconnect được; không hiển thị tiến độ giả |
| NFR-07 | Xóa và lưu giữ dữ liệu | Tombstone chặn truy cập/resume/late writes; cleanup và backup retention theo mục 7 |

## 8. Acceptance gates

Mã G0–G7 dùng thống nhất với các gói P0–P7 trong [Implementation Plan](../project/implementation-plan.md). Tại bản planning này, các gate **chưa có đủ bằng chứng nghiệm thu trên revision hiện tại**.

| Gate | Điều kiện đạt |
|---|---|
| G0 · nền tảng | DB sạch → migration head; dependencies/runtime tái lập; môi trường test tách broker/provider thật |
| G1 · quyền và lifecycle | Login/ownership negative cases; double start, broker lỗi, redelivery và cancellation đúng state; task A chờ vẫn tạo/chạy được task B; quota đồng thời đúng, không tạo output trùng |
| G2 · review có căn cứ | Web → evidence persist → REVIEW có citation; provider run thật trong cap; Critic/targeted search/no-delta/invalid-citation/hết cap dừng đúng |
| G3 · PDF và workspace | Web+PDF cùng task; upload không hợp lệ bị từ chối; UI thể hiện stage/wait/fail/partial và khôi phục snapshot |
| G4 · plan/protocol/resume | Assisted/automatic theo policy; protocol trung gian qua review/validation; WAITING_* resume sau restart đúng checkpoint/plan version, giữ độc lập task khác |
| G5 · experiment | CSV thật → metrics/charts; manifest tái lập đạt tolerance; run lỗi không sinh Results; evidence nối đúng input/config |
| G6 · tương tác và bàn giao | Q&A có nguồn/cap; revision giữ bản cũ và không dùng result lỗi thời; export có quyền; xóa task/cleanup đạt policy |
| G7 · đánh giá | Có baseline/ablation, rubric, quality/cost/latency/failures và limitations; tổng hợp evidence của G0–G6 |

Chi tiết cách đo: [Evaluation Plan](../project/evaluation-plan.md). Gate chưa đạt không được thay bằng mock rồi báo hoàn thành.

## 9. Ánh xạ yêu cầu sang kế hoạch

| Yêu cầu | Gói triển khai | Gate |
|---|---|---|
| FR-01 | P1; áp dụng tiếp cho routes mới P3–P6 | G1, kiểm hồi quy G3–G6 |
| FR-02 | P2 web; P3 PDF | G2, G3 |
| FR-03 | P2 plan schema; P4 approval/policy | G2, G4 |
| FR-04, FR-05, FR-10 | P2 evidence/loops/critic; áp dụng tiếp protocol/empirical | G2, G4, G5 |
| FR-06, FR-08 | P4 method/protocol/waits | G4 |
| FR-07 | P5 experiment | G5 |
| FR-09 | P2 REVIEW; P4 protocol trung gian; P5 bài tính toán và bài human-led sau nạp kết quả thật | G2, G4, G5 |
| FR-11 | P2 document lineage; P5 artifact lineage | G2, G5 |
| FR-12 | P1 events/log; P3 UI; P4–P5 wait/experiment stages | G1, G3–G5 |
| FR-13, FR-15 | P6 Q&A/revision/export; dữ liệu version nền từ P2 | G6 |
| FR-14 | Sau bản nộp; ADR-001 | Không phải gate 10/11 |
| FR-16 | Chuẩn bị dữ liệu trước; P7 chạy/chấm | G7 |
| FR-17 | P1 nhiều task/quota; P3 dashboard; P4 chờ/resume | G1, G3, G4 |
| NFR-01, NFR-02 | P1 nền; P3–P6 áp dụng và kiểm hồi quy | G1, G3–G6 |
| NFR-03, NFR-04 | P2 provider/fetch; P3 parser; P5 runner; P6 Q&A | G2, G3, G5, G6 |
| NFR-05, NFR-06 | P0 pin runtime; P1/P2 trace/profile; P3–P6 hoàn thiện | G0–G6 theo thành phần |
| NFR-07 | P3 storage/tombstone hooks; P6 delete/cleanup; P7 bàn giao | G6, G7 |
