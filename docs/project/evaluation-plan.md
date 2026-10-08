# Evaluation Plan — Đánh giá Multi-Agent Research

**Thiết kế cập nhật:** 09/10/2026 · **Trạng thái:** chưa chạy/chưa có kết quả.

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

## 4. Nghiệm thu experiment của sản phẩm

Routine đầu tiên `tabular_regression_v1` dùng CSV numeric, mean baseline và Ridge(alpha=1), split 80/20 seed 42 định trước. Fit imputer/scaler trên train; metric chính MAE, phụ RMSE; biểu đồ predicted-vs-actual và residuals. Tất cả mô hình cùng split; không dùng target làm feature.

- Lưu source/data checksum, column schema, seed, routine/code/container version, environment/dependency lock, config, timestamps/exit status.
- Gói output: metrics JSON/CSV, plots PNG, manifest, source routine hoặc launcher và hướng dẫn tái lập.
- Chạy lại cùng môi trường/input/config: metric dùng tolerance `abs <= 1e-8` hoặc `rel <= 1e-6`; plot so nội dung dữ liệu, không yêu cầu bytes PNG giống nếu metadata khác.
- Test không rò dữ liệu: preprocess fit train-only, không tune dựa hold-out. Sửa dữ liệu/cấu hình sau khi xem test phải tạo run mới có nhãn exploratory; không chỉ giữ run thắng.
- Dataset quá nhỏ, target thiếu/hằng, non-finite hoặc schema sai phải báo hạn chế/không chạy. Không suy ra causal inference hoặc statistical significance từ MAE thấp hơn trên một split.
- Technical retry giữ cùng config/seed; đổi phương pháp cần plan version mới. Kết quả âm/không cải thiện vẫn xuất báo cáo trung thực.

Tham khảo kỹ thuật: [scikit-learn — Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html). Routine cụ thể là lựa chọn phạm vi của ATI, không phải khuyến nghị áp dụng Ridge cho mọi nghiên cứu.

## 5. Acceptance matrix

| Nhóm | Gate | Các ca cần đạt | Bằng chứng |
|---|---|---|---|
| Environment | G0 | DB sạch lên head, dependencies pin, test dispatch/provider tách biệt | Revision/config, commands và outputs |
| Access/files | G1, G3 | Owner A/B; unauthorized event/download; malformed/oversize PDF/CSV | Automated checks + QA screenshots |
| Lifecycle | G1, G4 | Double start, broker fail, duplicate job, restart wait/resume, stale decision, cancel; WAITING_* chặn run thứ hai **cùng task** nhưng A chờ vẫn cho B chạy; 2 RUNNING/user, QUEUED không mất | DB transitions, event IDs, logs |
| Grounding | G2, G4, G5 | Invalid source/chunk, quote mismatch, no-source, contradictory sources, protocol/result provenance | Validator output + rubric |
| Budget/loops | G2, G5, G6 | Guard trước LLM/search/embed/retry; no-delta; 3 rounds/2 revisions; Q&A có cap riêng và không reset run budget | Usage ledger, stop reasons, kết quả kiểm tra |
| Runner/results | G5 | Real execution; failed/timeout run không Results; artifact integrity; reproduce | Input/config/output manifests + commands |
| Reports/chat | G6 | REVIEW/EMPIRICAL_COMPUTATIONAL/EMPIRICAL_HUMAN đủ cấu trúc; protocol chưa data không COMPLETED; Q&A citation; revision giữ bản cũ, thay data/config không dùng lại result cũ; authorized export | Version IDs, report snapshots |
| Retention/delete | G6 | Tombstone chặn read/resume/late writes; cancel tại safe boundary; cleanup retry và deadline 24 giờ, backup policy tối đa 7 ngày | Tombstone/cleanup timestamps, file/index/checkpoint inventory, cấu hình và kiểm retention |
| Evaluation bundle | G7 | Baseline/ablation đúng corpus/model/cap, rubric che nhãn, failures và hạn chế chấm một người; liên kết evidence G0–G6 | Frozen manifests, bảng chấm, kết quả và báo cáo |

Technical gates cần 100% ca bắt buộc đạt và không có citation sai lineage/Results bịa trong artifact được phát hành. Các chỉ số semantic/coverage là kết quả đo, không hứa “100% đúng”. Nếu baseline tốt hơn ATI, giữ kết quả và giải thích.

Mã gate theo [SRS §8](../requirements/SRS.md#8-acceptance-gates); mapping FR/NFR theo mục 9 của SRS. Bảng này mô tả cách kiểm, không phải kết quả đã đạt. Cleanup/retention dùng kiểm tra có clock/config được kiểm soát và evidence timestamp; không suy ra deadline đã đạt chỉ vì chức năng xóa trả HTTP thành công.

## 6. Lịch, ngân sách và báo cáo

Pilot trước 03/11; held-out 03–05/11; chấm/QA 05–07/11. Với (4 pilot + 8 held-out) × 3 cấu hình có tối đa 36 report runs trước reruns. Tổng cap evaluation phải được cấu hình riêng theo ngân sách dự án; số run/cap là kế hoạch, không phải cho phép tự tiêu tiền trong lượt cập nhật docs.

Lưu manifest câu hỏi/corpus/prompt/model/config/commit, output và logs redacted trong storage riêng; chỉ version kết quả/rubric đã bỏ dữ liệu riêng tư. Báo cáo kết quả gồm paired differences theo câu, trung bình/median, cost và failures; cỡ mẫu nhỏ không đủ để khẳng định ưu thế mọi lĩnh vực.
