# Evaluation Plan — Đánh giá Multi-Agent Research

**Cập nhật:** 02/11/2026 · **Trạng thái:** có nền CLI đóng băng/thu thập/chấm ở issue #79; chưa chạy benchmark khoa học, chưa có kết luận single-agent so với multi-agent.

Phân biệt hai việc: (A) người dùng dùng ATI chạy một thí nghiệm trên CSV; (B) đánh giá ATI để kiểm tra giá trị multi-agent. Kết quả A không thay thế bằng chứng B.

## 1. Câu hỏi nghiên cứu của đồ án

- RQ1: Với cùng corpus, model và cap, phối hợp vai trò có cải thiện độ hỗ trợ claim/bao phủ câu hỏi so với single-agent không?
- RQ2: Research loop tìm thiếu sót đem lại thay đổi gì về chất lượng so với cùng multi-agent workflow tắt macro loop? Chi phí/latency tăng bao nhiêu?
- RQ3: Người dùng có truy lại nguồn/kết quả, làm bài B khi bài A chờ dữ liệu và tiếp tục A sau restart mà không mất tiến độ không?

Giả thuyết đánh giá chỉ là dự kiến; không ghi “multi-agent tốt hơn” khi chưa đo. Một kết quả không tốt hơn vẫn có giá trị nếu báo cáo trung thực về trade-off.

## 2. Bộ dữ liệu và đối chứng

| Bộ | Quy mô dự kiến | Người chuẩn bị | Kiểm soát |
|---|---|---|---|
| Development/pilot | 4 câu hỏi | Chiến | Dùng chỉnh prompt/rubric, không tính vào kết quả cuối |
| Held-out review | 8 câu hỏi thuộc 2–3 chủ đề, có nguồn bất đồng/thiếu dữ kiện | Chiến | Freeze question/corpus/expected points trước khi chạy; có cả web snapshot và PDF text |
| Product experiment | 1 public numeric CSV không định danh + data dictionary | Chiến | URL/license/checksum/units/target; tối thiểu số hàng phù hợp split, quan sát độc lập và không phải time series/grouped samples; không claim data tổng hợp là dữ liệu thực |
| Negative cases | Input thiếu/sai, access chéo, no evidence, budget hết, retry/resume, A chờ/B chạy | Chiến | Assertions kỹ thuật và ghi nhận thao tác thực tế |

Ba cấu hình dùng cùng corpus đã freeze và cùng retrieval tool/index, không gọi live web trong phép so sánh chính:

| Nhãn | Cấu hình | Yếu tố kiểm soát |
|---|---|---|
| A | Single-agent dùng tools để retrieve và viết báo cáo | Cùng câu hỏi, corpus, model/version, output spec, tool/cost cap |
| B | ATI multi-agent đầy đủ, bounded critic/research loop | Cùng quyền truy cập corpus và giới hạn như A; retrieval có thể thay đổi theo nhu cầu |
| C | ATI như B, tắt macro research loop; giữ writer/critic revision | Cô lập đóng góp targeted re-retrieval; actual cost có thể thấp hơn |

Không ép actual token bằng nhau: báo cả chất lượng và chi phí thực dưới cùng cap. Live-search E2E được đo riêng vì web thay đổi khiến đối chứng không công bằng. Không tuning trên held-out sau khi xem kết quả; sửa bug thì ghi phiên bản và chạy lại mọi cấu hình bị ảnh hưởng.

## 3. Metrics và cách chấm

| Chỉ số | Định nghĩa / cách đo |
|---|---|
| Citation integrity | References có source/chunk tồn tại, đúng task và marker hợp lệ / tổng reference; kiểm toàn bài bằng code |
| Semantic claim support | Claim được evidence hỗ trợ đầy đủ / claims được chấm; nhãn supported/partial/unsupported/contradicted/unverifiable |
| Coverage | Expected points được trả lời có căn cứ / expected points theo rubric |
| Limitations/gap quality | Thang 0–2: nói rõ phạm vi, không khẳng định novelty tuyệt đối, nêu evidence cần bổ sung |
| Fabricated results | Số nhận định kết quả không có analysis artifact hoặc user-supplied provenance; strict gate = 0 |
| Research loop | Rounds, evidence delta sau dedup, lý do stop và cost tăng từng vòng |
| Cost/latency | Actual/estimated usage tách riêng; active duration, failures, timeouts; median/range cho mẫu nhỏ, không gọi p95 của vài run là SLA |
| Reliability | Duplicate start/resume, restart, cancel, ownership và artifact consistency tests |
| Usability | Hoàn thành 4 scenarios gồm A chờ/B chạy/A resume; lỗi/điểm bối rối; tự kiểm một người không phải user study đại diện |

Chiến chấm với nhãn A/B/C được che và thứ tự báo cáo xáo trộn; rubric/expected points đóng băng trước khi chạy held-out. Chọn có quy tắc 5 claims/report, gồm claim trung tâm, claim có số liệu nếu có, các claims ở đầu/giữa/cuối; tránh chỉ chọn câu dễ. Chấm một người có nguy cơ thiên lệch và không đo được đồng thuận giữa người chấm; phải công khai hạn chế này. Nếu có người đánh giá độc lập thực sự, lưu danh tính/vai trò và mức đồng thuận khi đã diễn ra, không ghi trước như kết quả. Bộ chính 8 × 3 = 24 report, khoảng 120 claims; đây là sample đánh giá, không phải kiểm chứng mọi câu.

Rubric limitations: 0 = thiếu hoặc phủ nhận giới hạn thực tế; 1 = nêu chung chung; 2 = nêu đúng giới hạn cụ thể của corpus/phương pháp/dữ liệu. Rubric gap: 0 = không có hoặc khẳng định novelty không có căn cứ; 1 = gợi ý có điều kiện nhưng cơ sở còn yếu; 2 = gap có nguồn, được giới hạn phạm vi và chỉ rõ cần kiểm chứng gì. Coverage chỉ tính expected point có đủ hỗ trợ; PARTIAL/UNVERIFIABLE không tính như SUPPORTED trong tỷ lệ claim support. Đây là quy tắc chấm đề xuất của đồ án, cần giữ nguyên trong protocol đã đóng băng.

## 4. Nghiệm thu experiment của sản phẩm

Routine đầu tiên `tabular_regression_v1` dùng CSV numeric, mean baseline và Ridge(alpha=1), split 80/20 seed 42 định trước. Triển khai hiện dùng complete-case filtering cho các cột đã đóng băng và học chuẩn hóa trên train, không có imputation; metric chính MAE, phụ RMSE; biểu đồ predicted-vs-actual và residuals. Tất cả mô hình cùng split; không dùng target làm feature.

- Lưu source/data checksum, column schema, seed, routine/code/container version, environment/dependency lock, config, timestamps/exit status.
- Gói output: metrics JSON/CSV, plots PNG, manifest, source routine hoặc launcher và hướng dẫn tái lập.
- Chạy lại cùng môi trường/input/config: metric dùng tolerance `abs <= 1e-8` hoặc `rel <= 1e-6`; plot so nội dung dữ liệu, không yêu cầu bytes PNG giống nếu metadata khác.
- Test không rò dữ liệu: preprocess fit train-only, không tune dựa hold-out. Sửa dữ liệu/cấu hình sau khi xem test phải tạo run mới có nhãn exploratory; không chỉ giữ run thắng.
- Dataset quá nhỏ, target thiếu/hằng, non-finite hoặc schema sai phải báo hạn chế/không chạy. Không suy ra causal inference hoặc statistical significance từ MAE thấp hơn trên một split.
- Technical retry giữ cùng config/seed; đổi phương pháp cần plan version mới. Kết quả âm/không cải thiện vẫn xuất báo cáo trung thực.
- Kiểm journal theo [đặc tả thí nghiệm](../technical/experiment-journal-and-reproducibility.md): `PLAN_FROZEN` phải có trước attempt; giữ tất cả attempts kể cả timeout/lỗi, `NO_IMPROVEMENT` và corrections; `TaskEvent` không thay journal. Ca nghiệm thu cố ý dùng dataset cho kết quả không cải thiện: vẫn có hai metrics và Results/Discussion đúng nhãn; lỗi kỹ thuật thì không có Results.
- Một execution thứ hai trong runner mới dùng đúng manifest để so MAE/RMSE/chart data và ghi `REPRODUCTION_CHECK` với sai khác. Cùng seed kiểm repeatability kỹ thuật, không chứng minh kết luận vững trên seed/dataset khác; nếu rerun lệch, giữ cả hai và không gắn nhãn “ATI đã tái lập”.

Tham khảo kỹ thuật: [scikit-learn — Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html). Routine cụ thể là lựa chọn phạm vi của ATI, không phải khuyến nghị áp dụng Ridge cho mọi nghiên cứu.

## 5. Acceptance matrix

| Nhóm | Gate | Các ca cần đạt | Bằng chứng |
|---|---|---|---|
| Environment | G0 | DB sạch lên head, dependencies pin, test dispatch/provider tách biệt | Revision/config, commands và outputs |
| Access/files | G1, G3 | Owner A/B; unauthorized event/download; malformed/oversize PDF/CSV | Automated checks + QA screenshots |
| Lifecycle | G1, G4 | Double start, broker fail, duplicate job, restart wait/resume, stale decision, cancel; WAITING_* chặn run thứ hai **cùng task** nhưng A chờ vẫn cho B chạy; 2 RUNNING/user, QUEUED không mất | DB transitions, event IDs, logs |
| Grounding | G2, G4, G5 | Invalid source/chunk, quote mismatch, no-source, contradictory sources, protocol/result provenance | Validator output + rubric |
| Budget/loops | G2, G5, G6 | Guard trước LLM/search/embed/retry; no-delta; 3 rounds/2 revisions; Q&A có cap riêng và không reset run budget | Usage ledger, stop reasons, kết quả kiểm tra |
| Runner/results | G5 | Real execution; failed/timeout run không Results; journal có plan trước chạy và mọi attempt; ca âm hợp lệ vẫn vào Results; artifact integrity; rerun độc lập đạt tolerance | Journal export, input/config/output manifests, hai execution và bảng sai khác |
| Reports/chat | G6 | REVIEW/EMPIRICAL_COMPUTATIONAL/EMPIRICAL_HUMAN đủ cấu trúc; protocol chưa data không COMPLETED; Q&A citation; revision giữ bản cũ, thay data/config không dùng lại result cũ; authorized export | Version IDs, report snapshots |
| Retention/delete | G6 | Tombstone chặn read/resume/late writes; cancel tại safe boundary; cleanup retry và deadline 24 giờ, backup policy tối đa 7 ngày | Tombstone/cleanup timestamps, file/index/checkpoint inventory, cấu hình và kiểm retention |
| Evaluation bundle | G7 | Baseline/ablation đúng corpus/model/cap, rubric che nhãn, failures và hạn chế chấm một người; liên kết evidence G0–G6 | Frozen manifests, bảng chấm, kết quả và báo cáo |

Technical gates cần 100% ca bắt buộc đạt và không có citation sai lineage/Results bịa trong artifact được phát hành. Các chỉ số semantic/coverage là kết quả đo, không hứa “100% đúng”. Nếu baseline tốt hơn ATI, giữ kết quả và giải thích.

Mã gate theo [SRS §8](../requirements/SRS.md#8-acceptance-gates); mapping FR/NFR theo mục 9 của SRS. Bảng này mô tả cách kiểm, không phải kết quả đã đạt. Cleanup/retention dùng kiểm tra có clock/config được kiểm soát và evidence timestamp; không suy ra deadline đã đạt chỉ vì chức năng xóa trả HTTP thành công.

## 6. Lịch, ngân sách và báo cáo

Pilot trước 03/11; held-out 03–05/11; chấm/QA 05–07/11. Với (4 pilot + 8 held-out) × 3 cấu hình có tối đa 36 report runs trước reruns. Tổng cap evaluation phải được cấu hình riêng theo ngân sách dự án; số run/cap là kế hoạch, không phải cho phép tự tiêu tiền trong lượt cập nhật docs.

Lưu manifest câu hỏi/corpus/prompt/model/config/commit, output và logs redacted trong storage riêng; chỉ version kết quả/rubric đã bỏ dữ liệu riêng tư. Báo cáo kết quả gồm paired differences theo câu, trung bình/median, cost và failures; cỡ mẫu nhỏ không đủ để khẳng định ưu thế mọi lĩnh vực.
Giữ đủ kết quả của A/B/C theo từng câu, kể cả multi-agent không cải thiện hoặc bị lỗi; không loại run bất lợi khỏi bảng tổng hợp mà không nêu lý do. Đây là nhật ký **đánh giá ATI**, tách với `ExperimentJournalEntry` của thí nghiệm người dùng.

## 7. Công cụ chuẩn bị và chấm đánh giá — issue #79

Nền CLI nằm ở `backend/app/evaluation`. Công cụ này **không gọi LLM/search, không tự chạy A/B/C, không cưỡng chế ngân sách runtime và không tạo ra kết quả benchmark thật**. Nó đóng băng protocol/corpus, thu các output đã chạy, kiểm cấu hình khai báo, tạo packet chấm che nhãn và tổng hợp điểm. Các adapter thực thi ba cấu hình với production workflow, bộ nguồn/câu hỏi thật và kiểm soát provider còn phải triển khai trước khi nghiệm thu G7. Các test dùng nguồn/bài/điểm giả ghi rõ `mode=smoke`, không được trình bày như một nghiên cứu thực tế.

### Quy trình và lệnh

Chạy trong container backend để dùng đúng dependency; mọi thư mục dưới `storage/` được Git ignore. Các đường dẫn là ví dụ, cần chọn thư mục mới cho mỗi protocol/packet/summary; công cụ từ chối ghi đè.

```text
docker compose exec -T backend python -m app.evaluation init storage/evaluation-input
docker compose exec -T backend python -m app.evaluation schema spec
docker compose exec -T backend python -m app.evaluation freeze storage/evaluation-input/spec.json storage/evaluations/protocol-v1
docker compose exec -T backend python -m app.evaluation record storage/evaluations/protocol-v1 storage/evaluation-input/run.json
docker compose exec -T backend python -m app.evaluation blind storage/evaluations/protocol-v1 storage/evaluations/pilot-packet --split pilot
docker compose exec -T backend python -m app.evaluation score storage/evaluations/protocol-v1 storage/evaluations/pilot-packet storage/evaluation-input/grades.json
docker compose exec -T backend python -m app.evaluation summarize storage/evaluations/protocol-v1 storage/evaluations/pilot-packet storage/evaluations/pilot-summary.json
```

`init` chỉ tạo một fixture smoke với model/revision mẫu; phải thay nguồn, câu hỏi, expected points, model/revision, retrieval/output contract, code revision và cap trước khi chuẩn bị pilot thật. `schema run` và `schema grade` xuất JSON Schema để tạo metadata/phiếu chấm đúng trường. Dùng `mode=pilot` cho 4 câu pilot hoặc `mode=study` cho 4 pilot + 8 held-out thuộc 2–3 chủ đề. Nguồn thật là file text UTF-8 có provenance URL/origin và ghi chú quyền sử dụng; nguồn synthetic chỉ được nhận ở smoke. Không xem ghi chú quyền hoặc nhãn `primary` do người nhập là một chứng nhận tự động về quyền/nội dung.

| Bước | Dữ liệu và kiểm tra |
|---|---|
| Freeze | Copy nội dung nguồn, hash text, câu hỏi/expected points, model/revision/temperature/output/retrieval/cap và code revision vào protocol có fingerprint; không đọc live web sau đó. Đường dẫn nguồn phải nằm trong thư mục spec. Ghi fingerprint vào biên bản trước khi chạy |
| Record | Mỗi case × arm × attempt có bản riêng, manuscript và trace snapshot. Arm cố định `single_agent`, `multi_agent`, `no_macro_loop`; C giữ micro revision và tắt macro loop. Sai model/control/source/cap hoặc có truy nguồn/embedding trực tuyến vẫn được giữ và đánh dấu không hợp lệ cho so sánh chính |
| Blind | Chỉ xuất một split; pilot packet không chứa câu hỏi/nguồn riêng của held-out. Giấu arm, model, cost, trace và verdict nội bộ của draft đã tạo; mapping giữ trong bundle riêng. Mỗi split chỉ có một primary packet để tránh đổi nhãn/chấm lại nhằm chọn điểm thuận lợi. Hoàn tất thu primary runs trước bước này |
| Score | Người chấm cung cấp quote nguyên văn từ manuscript, nhãn hỗ trợ và lý do, source quote, mọi expected point, điểm limitations/gap 0–2 và số fabricated results. Tối đa 5 claims theo quy tắc §3; ít hơn cần ghi lý do. Code kiểm quote có thật và nguồn thuộc corpus, không tự xác nhận semantic entailment hoặc chứng minh chọn mẫu không thiên lệch |
| Summarize | Lần **attempt=1** là kết quả chính; rerun không thay thế lần lỗi. Giữ planned/missing/failed/delivered/ungraded/control-invalid, trạng thái NEEDS_REVIEW/PARTIAL và số liệu chi phí/thời gian. Pair chỉ tính trên cùng câu có hai output hợp lệ đã chấm; giữ delta âm, không gộp pilot với held-out |

Không loại draft chỉ vì Critic đánh dấu `NEEDS_REVIEW` hoặc vì output `PARTIAL`: nếu đã có manuscript và đúng controls, vẫn chấm mức hỗ trợ/coverage như bản được giao. Khi chấm, trạng thái này được che thành `DELIVERED` để giảm lộ arm/verdict. Lỗi/thiếu output không có điểm chất lượng giả bằng 0; phải báo tỷ lệ lỗi và mẫu số đầy đủ cùng điểm trên tập chấm được. Mean support là trung bình theo report; pooled sample support là tổng claims SUPPORTED chia tổng claims được chấm. Chi phí tổng và median/range thời gian gồm cả run lỗi/không hợp lệ đã ghi, tách reruns khỏi kết quả chính. `strict_fabrication_gate` chỉ có kết quả khi toàn bộ packet đã được chấm; không đóng G7 chỉ dựa cờ này.

Nếu không có factual claim để chấm, ghi `claims=[]` và lý do thay vì bịa một claim: support/paired support delta là `null`, không tự gán 0 hoặc 1; coverage vẫn được chấm theo expected points. Summary báo số report và số cặp thực sự có support score. Rubric/expected points chỉ dành cho người chấm; bộ chạy agent tại §8 chỉ được đưa câu hỏi và corpus được phép vào prompt, không đưa đáp án/rubric vào ngữ cảnh sinh bài.

Metadata matching chỉ kiểm những gì bên chạy **khai báo**. Người điều phối phải đối chiếu trace với actual model/version, nguồn, network/calls và ledger trước khi xác nhận `controls_reviewed`; một JSON đúng schema không chứng minh runtime đã tuân thủ. Chấm chất lượng che nhãn nên làm trước khi xem mapping/trace. Một người làm cả điều phối và chấm phải công khai giới hạn blinding; văn bản manuscript vẫn có thể làm lộ phương pháp. Không dùng nhãn HUMAN nếu chỉ có model chấm. Alias model không có revision chính xác phải ghi `unavailable`, summary sẽ báo chưa pin đầy đủ.

Protocol, outputs, packet, key và grades dùng checksum và chống ghi đè, nhưng hash không phải chữ ký chống kẻ sửa đồng thời cả nội dung lẫn hash. Lưu thư mục private; trace/corpus có thể chứa dữ liệu riêng hoặc nội dung không được phép phát hành. Không commit chúng lên GitHub. Thay rubric/code/corpus hoặc đổi primary outputs sau blinding cần protocol có version mới, giữ bản cũ và công khai lý do; không tuning trên kết quả held-out. Báo cáo tóm tắt hiện là JSON để kiểm tra dữ liệu; UI/charts báo cáo và nghiên cứu so sánh thật vẫn là phần tiếp theo.

## 8. Chạy ba cấu hình trên nguồn cố định — issue #81

**Sau #84:** executor hiện yêu cầu contract v4. Freeze protocol/revision/fingerprint mới trước pilot; không dùng nhãn REVIEW-v3 cho code mới. Các con số nghiệm thu #81 dưới đây thuộc code lịch sử, không phải kết quả đánh giá chất lượng v4.

**Kiểm phần mềm 02/11/2026:** code `e457f17` / PR #82 có 485 backend tests, 20 frontend tests và 5/5 CI đạt; 60 ca focused evaluation và CLI plan trong Docker không gọi provider. Đây là bằng chứng bộ chạy, chưa phải kết quả pilot/held-out. Issue #83 tiếp tục thực nghiệm và chấm.

Bộ chạy `python -m app.evaluation.execute` thực hiện **một câu hỏi × một cấu hình × một attempt** mỗi lệnh. Không tự chạy toàn bộ 36 bài. Các tests dùng provider giả để kiểm phần mềm, không tạo kết quả nghiên cứu. Chỉ chạy thật khi đã chốt model, giá dùng làm trần tính chi phí, ngân sách tổng, câu hỏi và nguồn; không suy ra multi-agent tốt hơn từ các tests này.

| Cấu hình | Cách chạy đã triển khai |
|---|---|
| A — `single_agent` | Một controller lặp: chọn truy vấn truy xuất cục bộ hoặc trả bài hoàn chỉnh. Controller tự rút claims/quotes và viết; không gọi riêng Supervisor/Analyst/Writer/Critic. Dùng chung lưu chunk, đối chiếu quote và hậu xử lý; không bịa đánh giá Critic nên đầu ra cần người xem lại. Đây là baseline cụ thể, không đại diện mọi hệ thống single-agent |
| B — `multi_agent` | Chạy đúng `build_research_graph`, các node và validator của sản phẩm; thay các điểm kết nối provider/nguồn/database bằng context riêng. Giữ giới hạn hai vòng thu thập và hai lần sửa trong một vòng theo router hiện có |
| C — `no_macro_loop` | Cùng graph/node/model như B; chỉ đặt `max_iterations=0` để bỏ vòng tìm bổ sung. `max_micro_revisions=2` giữ nguyên. Không thay bằng pipeline viết lại đơn giản hơn |

Cả ba dùng cùng word/output profile đã đóng băng của Writer; adapter đánh giá vẫn giới hạn mỗi request tối đa 8192 output tokens cho mọi arm, ngoài các cap tổng. Cả ba dùng `output_contract=REVIEW-v4`, REVIEW narrative, STANDARD, MEDIUM (1400–2000 từ theo contract v4), IEEE; chỉ ngôn ngữ lấy từ controls. Contract này không phải template được một tạp chí cụ thể chứng nhận. Hồ sơ retrieval duy nhất hiện hỗ trợ là `frozen-lexical-v1-1024-128`: chunk 1.024 ký tự, chồng 128, truy xuất lexical xác định, cùng top ba chunk/truy vấn; không gọi embedding từ xa. Thứ tự đồng hạng dựa source tag/chunk index, không dựa UUID ngẫu nhiên. Mỗi snapshot tối đa 200.000 ký tự để không bị curator/researcher cắt ngầm. Đây là thí nghiệm đóng corpus và thay retrieval bằng adapter chung, **không** phải phép đo toàn bộ production retrieval/live search. Lựa chọn truy vấn và tập chunk thực nhận vẫn có thể khác theo controller/agents; đó là hành vi được đo dưới cùng quyền truy cập và cap.

Không truyền expected points, rubric, tên split hoặc đáp án cho model. Chỉ truyền câu hỏi, nguồn/chunk được phép và hướng dẫn output. Giữ đường dẫn thực `task → source → chunk → evidence → claim` trong database đánh giá; UUID không được giả làm evidence đã xác minh. Snapshot HTML/text chỉ được gắn phạm vi đã biết; không tự coi tài liệu web là bài báo đã đọc full text. Pilot bốn tài liệu chính thống đang chuẩn bị là **pilot kỹ thuật**, chưa thay bộ tám câu held-out với bài nghiên cứu thật.

### Trình tự chạy có kiểm soát

1. Chốt model có tài khoản hợp lệ. Transport hiện thực hiện OpenAI chat với một model/temperature cho mọi role, tắt cache/retry/fallback; không tự chuyển provider khi lỗi. Điều này chỉ giới hạn transport của thí nghiệm; sản phẩm vẫn có chuỗi provider riêng. Định giá input/output theo trần đã kiểm tra trên tài khoản, tính cả token suy luận có tính phí nếu áp dụng.
2. Sau khi code đã commit và kiểm thử, lấy `code_revision` cùng `executor_code_sha256` từ source sạch. Có thể in fingerprint bằng `python -c "from app.evaluation.execute import code_fingerprint; print(code_fingerprint())"`. Bổ sung vào spec rồi freeze. Fingerprint chuẩn hóa CRLF/LF và bao phủ toàn bộ Python trong `backend/app`. Chạy từ checkout cần backend sạch đúng commit; trong image cần biến `EVALUATION_CODE_REVISION` khớp và source fingerprint vẫn phải khớp. Biến môi trường là khai báo commit của image, không phải chữ ký chứng thực.
3. Tạo/migrate **database PostgreSQL riêng** có đoạn `eval` trong tên, ví dụ `synthia_eval_pilot`; dùng URL này cho tiến trình migration riêng, tuyệt đối không đổi database của API đang phục vụ. Đặt URL vào `EVALUATION_DATABASE_URL` của tiến trình chạy. Executor từ chối cùng tên DB với ứng dụng, từ chối DB có user/task chưa được đánh dấu là evaluation, và gắn DB với đúng protocol. Không cần giữ worker/API chạy cho từng slot.
4. Chạy lệnh dưới đây **không** có `--execute` để xem kế hoạch. Giá và ngân sách trong ví dụ là placeholder, phải thay bằng giá trần đã xác minh và ngân sách đã chốt; không chạy nguyên văn.

```text
python -m app.evaluation.execute storage/evaluations/protocol-v1 --case CASE_ID --arm multi_agent --campaign-cap TOTAL_USD --input-rate INPUT_USD_PER_MILLION --output-rate OUTPUT_USD_PER_MILLION
```

5. Sau khi xác nhận cấu hình cụ thể, thêm `--execute` để chạy đúng slot đó. Lặp với `single_agent` và `no_macro_loop`, cùng bundle/campaign/prices/cap; hoàn tất pilot trước held-out. Fixture smoke bị chặn khi dùng transport thật. Mỗi lỗi vẫn có run/trace; rerun chỉ dùng `--attempt 2` trở lên, không thay attempt đầu.
6. Thu xong các primary runs mới tạo packet che nhãn và chấm theo §7. Kiểm trace/controls riêng với chấm chất lượng. Không nâng `main` hay đóng G7 khi chỉ qua tests hoặc mới có output chưa chấm.

### Chi phí, lỗi và bằng chứng

Campaign có lock chống hai tiến trình dùng cùng ledger. Giữ nguyên tổng cap/giá/protocol qua các lần gọi; trước **mọi** request phải ghi reservation xuống disk. Kiểm call/token/time/cost cap theo run và tổng cost campaign trước request. Khi có usage thật, lưu usage cùng revision/finish reason; nếu provider lỗi, timeout, mất metadata hoặc tiến trình chết, giữ charge dự phòng để tránh tính thành miễn phí. Phần input dự phòng dùng byte count có framing/schema overhead; đó là ước lượng bảo thủ, không phải tokenizer đo chính xác hay cam kết hóa đơn. Usage vượt reservation được ghi vi phạm và chặn request tiếp theo. Đơn giá do người vận hành cấu hình là cơ sở **estimated cost**; cần đối chiếu hóa đơn, không tuyên bố kiểm soát được mọi thay đổi giá của provider.

Ledger nằm ở `bundle/campaign`, output ở `bundle/executions`, collector ở `bundle/runs`. Không ghi đè run. Lock còn sau crash phải kiểm tra tiến trình/ledger/run đã dừng trước khi phục hồi; không xóa ledger để cấp lại ngân sách. Giữ mọi status `FAILED`, `TIMEOUT`, `BUDGET_EXCEEDED`, `NEEDS_REVIEW`, `PARTIAL`, usage ước lượng và kết quả bất lợi. Bản thảo trước lỗi vẫn được lưu, nhưng run lỗi không biến thành kết quả thành công để chấm chính.

`network_calls=0` trong protocol collector nghĩa là **không truy cập mạng để bổ sung nguồn/embedding**. Request LLM vẫn cần mạng; trace ghi riêng `llm_transport_attempts`. Trace còn có role, truy vấn, chunk ID, loop/stop reason, usage/revision và claims; tắt LangSmith tracing trong context đánh giá để không vô tình gửi dữ liệu ra telemetry. AgentRun trong DB đánh giá đánh dấu usage lấy từ trace, không dùng các con số heuristic cũ làm kết quả đo. Hash và metadata giúp kiểm lại; reviewer vẫn phải kiểm tra thực thi và chất lượng, chúng không tự chứng minh ngữ nghĩa đúng hoặc môi trường production đã an toàn.
