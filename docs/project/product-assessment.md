# Rà soát và chốt định hướng — Multi-Agent Research System

**Ngày chốt thiết kế:** 08/10/2026 · **Mốc nộp:** 10/11/2026 · **Code được rà:** `ebb525a`.

Đây là review tĩnh code/tài liệu, không phải biên bản chạy hệ thống. Quyết định này thay scope v3.0 còn để thí nghiệm thật là tùy chọn. [SRS v4.0](../requirements/SRS.md) là yêu cầu hiện hành; [Implementation Plan](implementation-plan.md) là thứ tự thực hiện.

## 1. Kết luận và tên đề tài

**Multi-Agent Research System — Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập.**

Ma trận function/stack/pattern và ranh giới implementation hiện có so với target: [Technical Design](../architecture/technical-design.md).

ATI giúp người dùng đi từ câu hỏi và nguồn riêng đến tổng hợp tài liệu, gợi ý khoảng trống nghiên cứu, phương pháp, kết quả phân tích/thí nghiệm được hỗ trợ và bản thảo bài báo đầy đủ cấu trúc. Giá trị cốt lõi là phối hợp các agent chuyên trách trên bằng chứng chung, phản biện có vòng lặp và lưu căn cứ của kết quả.

Hướng này phù hợp đề tài và góp ý giảng viên. Thu hẹp **năng lực thực thi**, không thu hẹp mọi câu hỏi vào AI/ML: review và protocol nhận câu hỏi nhiều lĩnh vực; thực thi trước hạn chỉ hỗ trợ một loại thí nghiệm CPU trên dữ liệu bảng. Hỗ trợ một lĩnh vực không đồng nghĩa đã được đánh giá chuyên môn trong lĩnh vực đó.

| Đường nghiên cứu | Đầu vào | Đầu ra cần chạy được trước hạn |
|---|---|---|
| Tổng quan có nguồn | Câu hỏi, web, PDF có text | Bài tổng quan có phạm vi tìm kiếm, đối chiếu nguồn, gợi ý khoảng trống, giới hạn và citations |
| Thực nghiệm tính toán | CSV không định danh; câu hỏi dự đoán đại lượng số | So sánh baseline và phương pháp cho phép; số liệu/bảng/biểu đồ thật; bản thảo thực nghiệm và gói tái lập |
| Nghiên cứu ngoài hệ thống | Câu hỏi cần lab/khảo sát/thực địa | Protocol/checklist và bài protocol; chờ dữ liệu, nhận CSV phù hợp để tiếp tục phân tích |

“Bài báo hoàn chỉnh” là bản thảo đủ cấu trúc và có căn cứ theo loại bài. Không đồng nghĩa peer-reviewed, chứng minh tính mới hoặc được tạp chí nhận. Thiếu dữ liệu phải trả protocol/partial, không điền giả Results.

## 2. Điểm tốt giữ lại

- FastAPI, Celery/Redis, LangGraph và PostgreSQL/pgvector phù hợp tác vụ dài, có trạng thái và vòng lặp.
- Source → chunk → evidence → claim dùng chung cho review, hỏi đáp và viết bài.
- Phân biệt hệ thống tính toán với nghiên cứu ngoài đời giúp giữ phạm vi nhiều lĩnh vực.
- Bounded loops, ownership và trạng thái chờ bền vững đã có trong định hướng.
- Ba thành viên không code đóng góp trực tiếp vào dữ liệu đánh giá, kiểm nguồn và QA sử dụng.

## 3. Điểm cần sửa trong định hướng

| Vấn đề | Hệ quả | Quyết định |
|---|---|---|
| Scope gần “co-scientist mọi lĩnh vực”, experiment tùy chọn | Khó chứng minh yêu cầu chạy thực nghiệm | Một thí nghiệm hẹp chạy thật là acceptance gate; phương pháp khác đi protocol |
| Đếm mọi node/tool thành agent | Khó giải thích lợi ích multi-agent | 7 agent roles; Curator, Runner, Validator là mô-đun code |
| Chưa đo đóng góp đa tác tử | Nhiều prompt nhưng chưa biết có tốt hơn baseline | Single-agent cùng nguồn + multi-agent + ablation bỏ research loop |
| Planning thiếu contract/DoD | AI code dễ tự đổi API/schema hoặc báo done sớm | Gói P0–P7 có phụ thuộc, đầu ra, phép kiểm tra và gate |
| Hỏi đáp/sửa bài/auto mode còn mờ | Chưa đáp ứng tương tác ít bước | Q&A theo report version; sửa tạo version mới; automatic mode theo policy/cap |
| Runner chưa chọn | Treo experiment tới cuối kỳ | Docker runner riêng chỉ chạy routine do dự án viết/duyệt; phạm vi demo kiểm soát |
| Diagram thiếu event return, DFD store → user, protocol bỏ Critic | Luồng sai hoặc thiếu | Sửa luồng, giữ một sơ đồ kiến trúc hoàn chỉnh không chia phase |

## 4. Findings từ code và ảnh hưởng triển khai

Mức P0/P1 ở cột đầu là độ ưu tiên review, khác với mã gói triển khai P0–P7.

| ID / mức | Bằng chứng source | Vấn đề | Gói |
|---|---|---|---|
| R1 · P0 | [research.py](../../backend/app/api/v1/endpoints/research.py), dummy user và các route | Registration chưa phải authentication; chưa filter owner | P1 |
| R2 · P0 | [worker.py](../../backend/app/worker.py), initial_state; [nodes.py](../../backend/app/agents/nodes.py), ainvoke | Budget lưu ở task nhưng không truyền/guard từng call, retry/fallback chưa tính chung | P1–P2 |
| R3 · P0 | [nodes.py](../../backend/app/agents/nodes.py), analyst/post_processor | Extraction không mang UUID source/chunk hoặc persist chain; post-processor trả nguyên draft và COMPLETED | P2 |
| R4 · P1 | [nodes.py](../../backend/app/agents/nodes.py), critic; [graph.py](../../backend/app/agents/graph.py) | Critic chỉ đọc 3.000 ký tự, không có evidence; hết loop vẫn finalize; thiếu evidence-delta stop | P2 |
| R5 · P1 | [research.py](../../backend/app/api/v1/endpoints/research.py), start; [worker.py](../../backend/app/worker.py) | Thiếu transition/lock/idempotency; DB commit trước enqueue; acks_late không tự chống chạy lặp | P1 |
| R6 · P1 | [graph.py](../../backend/app/agents/graph.py), compile; [worker.py](../../backend/app/worker.py) | Chưa có checkpointer/thread ID/interrupt; worker không phân biệt pause với thiếu report | P4 |
| R7 · P1 | [embedder.py](../../backend/app/tools/embedder.py), [source.py](../../backend/app/models/source.py) | Không pin/lưu embedding profile theo corpus; đổi provider có thể dùng vectors không tương thích | P2 |
| R8 · P1 | [report.py](../../backend/app/models/report.py), unique report/task; UI detail | Không có versioning; polling chưa phân biệt stage/lifecycle và partial/wait | P2 nền version, P3–P4 UI/state, P6 revision |
| R9 · P1 | [scraper.py](../../backend/app/tools/scraper.py), manifests | SSRF guard cần chống DNS rebinding/response quá lớn; Python root 3.14 khác Docker 3.11, dependencies chưa khóa | P0, P2–P3 |
| R10 · P1 | [test_api_workflow.py](../../backend/tests/test_api_workflow.py) | Tên E2E nhưng chỉ kiểm API; gọi start mà không cô lập dispatch/provider, không chứng minh report thành công | P0–P2 |
| R11 · P2 | [nodes.py](../../backend/app/agents/nodes.py), curator/global cache | Sửa db_id trong state lồng nhau, xử lý list tích lũy; cache global chưa rõ scope owner/run/retention | P2–P3 |

Đây là review tĩnh, không khẳng định đã khai thác lỗi hoặc chạy lại runtime. Không sửa runtime code trong đợt chốt planning này.

## 5. Giá trị của multi-agent cần chứng minh

Supervisor chia câu hỏi thành nhu cầu bằng chứng. Researcher tìm câu trả lời/counterevidence; Evidence Analyst tổng hợp và gợi ý khoảng trống. Methodologist/Data Analyst tham gia khi cần protocol/thí nghiệm. Writer nhận evidence bundle; Critic nhận draft, kế hoạch, evidence và results để chỉ ra lỗi. Bộ điều khiển bằng code quyết định sửa/tìm tiếp/dừng theo budget.

Dùng cùng LLM cho nhiều vai trò vẫn hợp lệ nếu tách nhiệm vụ, context, output và trace. Chạy song song API search không tự chứng minh multi-agent tốt hơn. Xem [Evaluation Plan](evaluation-plan.md).

## 6. Đối chiếu tham khảo đã đọc 08/10

| Nguồn | Bài học cho ATI | Giới hạn áp dụng |
|---|---|---|
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Vai trò phối hợp, web/local sources, report và progress | Không coi mô tả repo là benchmark ATI |
| [STORM](https://github.com/stanford-oval/storm) | Thu thập nhiều góc nhìn, tổ chức bài có citations | Bài tổng hợp không tự thành thực nghiệm |
| [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | Nối ý tưởng, thực nghiệm, artifacts và manuscript | Tree search/GPU/code tùy ý ngoài bản nộp |
| [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Orchestration/evaluator loop phải có mục đích và đánh giá | Không thêm agent chỉ để tăng số lượng |

Đây là suy luận thiết kế theo nhu cầu ATI, không tuyên bố ATI mới hơn/mạnh hơn các hệ thống tham khảo.

## 7. Cam kết và rủi ro tiến độ

Chốt modular monolith + worker nền + shared evidence + routine runner riêng theo [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md). Từ 08/10 đến 10/11 còn 33 ngày lịch; lịch giả định Chiến có khoảng 3–4 giờ tập trung/ngày. Cập nhật ước lượng theo gate thực tế.

Nếu trễ, cắt ảnh, export trang trí và độ rộng template trước. Nếu experiment không đạt an toàn/tái lập, ghi rõ chưa đạt và điều chỉnh cam kết với giảng viên; không gọi protocol/mock là thí nghiệm đã chạy. Scope mới đóng băng từ bản này.

Theo dõi việc hiện thực hóa bằng mapping FR/NFR → P0–P7 → G0–G7 tại [SRS §8–9](../requirements/SRS.md#8-acceptance-gates). Việc đồng bộ tài liệu không đóng các findings code; chỉ đóng khi có thay đổi và evidence tương ứng.
