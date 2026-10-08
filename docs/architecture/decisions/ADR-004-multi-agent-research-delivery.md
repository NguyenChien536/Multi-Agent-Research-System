# ADR-004: Kiến trúc và phạm vi triển khai Multi-Agent Research

**Trạng thái:** Chốt thiết kế 08/10/2026, bổ sung article-first/multi-task lifecycle 09/10/2026; implementation phải qua gates.<br>
**Thay thế:** release constraint của ADR-003 còn để experiment tùy chọn; giữ ranh giới human-led research.<br>
**Phạm vi:** bản nộp 10/11 và nền mở rộng.

## Bối cảnh

Code `ebb525a` có API, graph với micro/macro loop và lưu nguồn. Chưa có auth/ownership đầy đủ, durable interrupt, budget guard hoặc citation validator thật. Một developer còn 33 ngày lịch; cần chốt experiment và đo lợi ích multi-agent.

## Quyết định

1. **Định vị/đầu ra:** đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập; REVIEW/EMPIRICAL_COMPUTATIONAL/EMPIRICAL_HUMAN đều hướng tới **bản thảo bài báo hoàn chỉnh**. Protocol human-led là artifact trung gian, không đánh dấu bài hoàn thành khi thiếu dữ liệu/kết quả thật. Q&A và revision ở workspace từng bài.
2. **Modular monolith:** một backend codebase, API/worker process riêng; giữ FastAPI, Celery/Redis, LangGraph, PostgreSQL/pgvector. Không tách agent thành microservice; chưa cần Kafka/Kubernetes/vector DB thứ hai/long-term agent memory.
3. **7 agent roles:** Supervisor, Researcher, Evidence Analyst, Methodologist, Data Analyst, Writer, Critic. Evidence Analyst kiêm synthesis/gap. Curator, router, validator, budget manager, runner là code; review không bắt buộc gọi role thực nghiệm.
4. **State và nhiều bài:** DB giữ Task/ResearchRun/plan/report versions/artifact metadata; PostgreSQL checkpointer cùng DB nhưng namespace riêng. Checkpoint chủ yếu chứa IDs/counters. Một active run/task, nhiều task/user; WAITING_* không giữ worker/quota RUNNING và không chặn task khác. Mặc định tối đa 2 job RUNNING/user, QUEUED đợi bền vững theo dispatcher. Claim/lease chống worker chạy trùng, decision/upload unique keys.
5. **Dispatch/events:** task/run + outbox cùng transaction; dispatcher nền trong API lifespan publish và retry khi broker trở lại. Nhiều API replica phải claim outbox bằng DB lock/lease. Delivery at-least-once, worker dedup/CAS và output unique; không hứa exactly-once provider calls. TaskEvent lưu DB; Pub/Sub chỉ báo có cập nhật; SSE replay/snapshot có ownership, polling fallback.
6. **Budget/providers:** adapter bọc LLM/search/embedding/retry/fallback, reserve trước/reconcile sau. Pin model và embedding profile; đổi profile cần re-index. Cache private scoped hoặc tắt; fallback trong allowlist/data policy.
7. **Experiment bắt buộc:** `tabular_regression_v1`, CSV numeric; mô tả dữ liệu, DummyRegressor(mean) vs Ridge(alpha=1), split 80/20 seed 42 định trước, MAE chính/RMSE phụ. Preprocessing chỉ fit train. Không lặp để tìm kết quả đẹp hoặc tuyên bố nhân quả/novelty.
8. **Runner:** container Docker riêng cho routine do dự án viết/duyệt, non-root, no network, drop capabilities/no-new-privileges, read-only rootfs, resource/time/output limits. API/worker không mount Docker socket. Operator/launcher tin cậy trên host khởi động job container từ manifest và staging directory theo job. Adapter cho phép dùng managed sandbox sau này; không nhận code LLM tùy ý và không gọi là production sandbox.
9. **Files:** private local volume qua ArtifactStore cho demo, metadata/checksum/owner ở DB; UI qua API authorized download. Target deployment có thể dùng S3-compatible object storage cùng interface, không buộc thêm MinIO trước hạn.
10. **Observability:** JSON logs, AgentRun, TaskEvent và task detail UI bắt buộc. OTel/Grafana/LangSmith tùy chọn; không gửi raw private content tới tracing bên ngoài mặc định.
11. **Loops và completion:** tối đa 3 vòng thu thập gồm vòng đầu, 2 writer revisions gồm citation repairs; no-evidence-delta thì dừng. Missing data phải chờ; unsupported method trả hướng dẫn/protocol trung gian và yêu cầu sửa, không giả định Results. Protocol cũng qua Critic/Validator nhưng không đi tới COMPLETED. Bài empirical chỉ COMPLETED sau khi có kết quả thật, provenance và đủ sections.

## Lựa chọn và đánh đổi

| Lựa chọn | Quyết định |
|---|---|
| Chỉ deep research report | Là lát cắt đầu, chưa đủ yêu cầu experiment thật |
| Full AI Scientist/tree search/code tùy ý | Sau bản nộp; cần sandbox mạnh, budget và đánh giá lớn hơn |
| Managed sandbox ngay | Adapter hỗ trợ đổi sau; chưa bắt mua thêm dịch vụ chỉ để chạy routine tin cậy |
| Agent microservices | Không cần cho một developer, tăng deploy/giao tiếp/debug |
| Queue không có idempotency/outbox | Không chọn; DB commit và broker publish có thể lệch, delivery có thể lặp |

Giữ stack hiện có, nhưng phải làm run/versioning, dispatch reliability, guard và lineage trước khi thêm role. Runner chỉ phù hợp routine và input limits đã xác minh trong môi trường kiểm soát; host launcher là trust boundary.

Nếu runner chưa đạt gate, ghi feature chưa đạt; không dùng mock như kết quả thực. Run thật có manifests/metrics/charts và đánh giá baseline là nghiệm thu bắt buộc.

## Tham khảo

- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Celery — Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [Docker — Security](https://docs.docker.com/engine/security/)
- [scikit-learn — Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)
- [pypdf — Extract text from a PDF](https://pypdf.readthedocs.io/en/latest/user/extract-text.html)
- [Technical Design](../technical-design.md): chức năng, công nghệ, design patterns và hiện trạng source
- [SRS](../../requirements/SRS.md), [System Design](../system-design.md), [Implementation Plan](../../project/implementation-plan.md)
