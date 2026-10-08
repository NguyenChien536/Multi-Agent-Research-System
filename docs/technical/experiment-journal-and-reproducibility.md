# Nhật ký thí nghiệm và khả năng tái lập

**Trạng thái:** đặc tả mục tiêu 09/10/2026; chưa được triển khai hoặc nghiệm thu. Phạm vi bản nộp chỉ có routine `tabular_regression_v1` trên CSV số. [ADR-005](../architecture/decisions/ADR-005-experiment-journal-and-reproducibility.md) ghi quyết định; [Evaluation Plan](../project/evaluation-plan.md) ghi phép kiểm.

## 1. Học gì từ AI Scientist

AI Scientist ghi kết quả, biểu đồ và quan sát của từng thí nghiệm vào *experimental journal* để quyết định bước tiếp theo và viết bài; các lần chạy lặp với seed khác giúp đánh giá độ ổn định. Bài báo do hệ thống tạo có thể nêu kết quả âm, nhưng bản thân việc ghi nhật ký không bảo đảm nghiên cứu đúng hoặc được công bố. ATI lấy **nguyên tắc ghi đầy đủ, kiểm được và không chọn lọc kết quả**; không sao chép phạm vi tự viết/chạy mã tùy ý của dự án đó vào bản nộp.

- [Nature — Towards end-to-end automation of AI research](https://www.nature.com/articles/s41586-026-10265-5)
- [Sakana AI Scientist v2 — source và cảnh báo chạy mã AI tạo](https://github.com/SakanaAI/AI-Scientist-v2)

## 2. Ba lớp ghi nhận khác nhau

| Lớp | Nội dung | Mục đích |
|---|---|---|
| `TaskEvent`/`AgentRun` | stage, role, thời gian, chi phí, lỗi vận hành | UI progress, điều tra hệ thống; không là bằng chứng cho Results |
| `ExperimentJournalEntry` | plan đóng băng, lần thử, quan sát, diễn giải, kiểm tái lập; liên kết run/artifact | Sổ nghiên cứu đọc được theo thời gian; chỉ append, không sửa kết quả cũ |
| Runner log + artifact | stdout/stderr đã che dữ liệu, metrics JSON/CSV, chart data/PNG, manifest, input | Kiểm kỹ thuật và chứng cứ có checksum; private theo owner/task |

Journal thuộc `ResearchTask` và `AnalysisRun`; mỗi entry có `entry_id`, `task_id`, `analysis_run_id`, `attempt_id` khi có, `sequence`, `kind`, `created_at`, `actor` (human/system/agent role), `plan_version`, `payload` có schema/version, `artifact_ids` và checksum. Lần chạy gốc và lần kiểm lại là hai execution/attempt IDs khác nhau dưới cùng experiment spec, không ghi đè output nhau. Unique `(analysis_run_id, sequence)`; idempotency key chống worker ghi lặp. Chỉ cho append/correction entry mới có lý do và tham chiếu entry cũ; không ghi đè. Người dùng xem timeline đã lược bỏ secrets; export cùng gói thực nghiệm. Xóa task xử lý journal như dữ liệu riêng của task theo NFR-07.

## 3. Trình tự của một thí nghiệm

1. **Trước khi chạy:** lưu `PLAN_FROZEN` với câu hỏi/giả thuyết có thể kiểm, CSV checksum/license/schema, target/features, baseline, Ridge, MAE chính/RMSE phụ, split 80/20, seed 42, điều kiện loại trừ và routine version. Đây là bản pre-run, không được đổi sau khi thấy test. Đổi câu hỏi, metric, data hoặc phương pháp tạo plan/analysis version mới và giữ bản cũ.
2. **Mỗi attempt:** lưu `STARTED` cùng manifest hash, môi trường/image digest/dependency lock và timestamp; khi kết thúc lưu `EXECUTION_RESULT` với exit status, error code, input/output checksum, metrics/artifact IDs, runtime và giới hạn đã chạm. Retry kỹ thuật giữ manifest, có attempt ID riêng; lần lỗi vẫn còn trong journal.
3. **Sau kiểm dữ liệu:** validator xác nhận schema/finite metrics/lineage, rồi lưu `OBSERVATION`. Kết luận `IMPROVEMENT`, `NO_IMPROVEMENT` hoặc `INCONCLUSIVE` là diễn giải so với baseline theo metric đã đóng băng; không đồng nhất với trạng thái chạy. `TECHNICAL_FAILURE`/`INVALID_INPUT` là lỗi hoặc dữ liệu không đủ, không gọi là “kết quả âm”.
4. **Diễn giải:** Data Analyst ghi `INTERPRETATION` tham chiếu entry/artifact đã kiểm và nêu giới hạn; Writer đưa mọi kết quả liên quan vào Methods/Results/Discussion. Critic kiểm trường hợp chọn lọc run thuận lợi, đổi giả thuyết sau kết quả và tuyên bố nhân quả/thống kê quá mức.
5. **Kiểm tái lập:** chạy lại từ manifest đóng băng trong runner mới, lưu `REPRODUCTION_CHECK` riêng, so sánh metric và chart data; ghi `PASSED`, `FAILED` hoặc `NOT_RUN` cùng sai khác. Không ghi “ATI đã tái lập” nếu chỉ có manifest hoặc lần chạy đầu.

Đầu ra âm hợp lệ vẫn có Results và bài empirical có thể hoàn thành nếu các gate khác đạt. Lỗi kỹ thuật/invalid input không sinh Results. Bản thảo phải nêu cả số liệu baseline lẫn Ridge, không chỉ mô hình tốt hơn. Một split không chứng minh ý nghĩa thống kê, khả năng tổng quát hoặc không tồn tại hiệu quả; `NO_IMPROVEMENT` chỉ là kết luận trong phép đo đã định.

## 4. Hợp đồng manifest và phép kiểm

Manifest bất biến gồm `manifest_version`, `task/run/analysis IDs`, `plan_version`, `routine ID+source commit`, `image digest`, `dependency lock hash`, `input artifact checksum` và schema/data dictionary, cấu hình/seed/split, metric definitions, timestamps, output artifact IDs/checksums và exit status. Hash manifest nội dung trước chạy không chứa output; manifest kết quả tham chiếu hash này và các output. Lưu artifact private, chỉ owner tải qua API có quyền. Nếu dependency/image không pin được, đánh dấu giới hạn thay vì tuyên bố tái lập.

Chạy lại **cùng** input/config/routine/environment trong runner mới kiểm *repeatability* của routine: MAE/RMSE với `abs ≤ 1e-8` **hoặc** `rel ≤ 1e-6`; chart so bảng dữ liệu sinh biểu đồ, không so PNG byte. Ghi lệnh, environment, hash và sai khác của cả hai lần. Nếu không đạt, giữ cả hai kết quả và chặn nhãn “đã tái lập”; điều tra trước khi phát hành claim số liệu. Chạy **seed/dataset khác** là kiểm độ vững/replication khoa học, chỉ là mở rộng sau khi có phương pháp và đánh giá phù hợp; không lấy lần chạy cùng seed để tuyên bố tổng quát.

Với dữ liệu thí nghiệm ngoài hệ thống, ATI lưu người cung cấp, nguồn, protocol, đơn vị, thời điểm, file hash, **cả kết quả không ủng hộ giả thuyết** và hạn chế xác minh. Nếu file đi qua routine ATI hỗ trợ, phân tích lại thành `AnalysisRun` riêng; nếu không, giữ artifact/provenance ở task và ghi `USER_SUPPLIED_NOT_REPRODUCED`. Writer vẫn trình bày kết quả âm có thật với nhãn nguồn và giới hạn, không loại bỏ vì không thuận lợi. Không tự tạo journal entry như thể ATI đã làm lab/khảo sát.

## 5. Điều kiện mở rộng sang mã do AI tạo

Đây là **future work**, không thuộc gate 10/11. Routine dự án viết và duyệt chạy trong Docker giới hạn không chứng minh khả năng chạy mã LLM tùy ý an toàn. Chỉ xét mở sau khi có tất cả:

1. Threat model cho mã không tin cậy; runner cô lập mạnh được đánh giá, không cấp Docker socket/host mounts/secrets, network tắt mặc định, giới hạn CPU/RAM/time/output và cleanup; thử các ca vượt quyền, thoát sandbox, lạm dụng tài nguyên và exfiltration. Chọn công nghệ qua ADR riêng, không mặc định Docker là đủ.
2. Hợp đồng experiment và journal nêu trên hoạt động với mọi attempt, lỗi và kết quả âm; code/dataset/dependencies/artifacts được pin và kiểm integrity; user có thể xem code và phạm vi chạy.
3. Bộ đánh giá đóng băng gồm bài toán đa dạng, ca âm, ca lỗi, rerun, chất lượng kết luận, chi phí và latency; người đánh giá xác nhận các giới hạn. Không mở rộng chỉ dựa một demo thành công.
4. Quyền/hạn mức thực thi, xác nhận của người dùng khi cần, audit và incident/kill switch rõ. Không tự ghi vào bài báo rằng thí nghiệm đã được xác nhận khoa học chỉ vì runner chạy xong.

Nguồn ranh giới kỹ thuật: [Docker Engine security](https://docs.docker.com/engine/security/). Cách báo cáo dữ liệu/code/protocol cũng cần theo quy định của lĩnh vực và nơi nộp; xem [Nature Portfolio reporting standards](https://www.nature.com/nature/editorial-policies/reporting-standards).
