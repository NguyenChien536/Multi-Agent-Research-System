# Báo cáo Tiến độ Giữa kỳ

**Tên đề tài:** Hệ thống đa tác tử hỗ trợ nghiên cứu có bằng chứng và thực nghiệm tái lập<br>
**Tên tiếng Anh:** Multi-Agent Research System (ATI)<br>
**Thời gian thực hiện:** 10/09/2026–10/11/2026 · **Planning cập nhật:** 08/10/2026

| STT | Họ tên | MSSV | Trách nhiệm |
|---:|---|---|---|
| 1 | Nguyễn Đình Chiến | [Nhóm bổ sung] | Trưởng nhóm, kế hoạch, kiến trúc, code/tích hợp, xác minh kỹ thuật |
| 2 | Phạm Long Vũ | [Nhóm bổ sung] | Query/source set, dataset, rubric và QA thủ công |
| 3 | Nguyễn Văn Hiếu | [Nhóm bổ sung] | User scenarios, flow, demo checklist và issue log |
| 4 | Nguyễn Thị Hải My | [Nhóm bổ sung] | Related work, nguồn, chấm nội dung và biên tập |

**Giảng viên:** [Nhóm bổ sung] · **Ngày nộp báo cáo:** [Nhóm bổ sung]

## 1. Overview — Tổng quan

ATI hỗ trợ người nghiên cứu từ câu hỏi và nguồn riêng tới tổng quan có bằng chứng, gợi ý khoảng trống nghiên cứu, phương pháp và bản thảo đúng loại. Các agent phân vai tìm nguồn, phân tích, thiết kế phương pháp, viết và phản biện; graph điều phối bằng state/guards. Người dùng xem agent đang làm gì, hỏi về bài và yêu cầu sửa trong cùng workspace.

| Đường nghiên cứu | Hệ thống thực hiện | Đầu ra |
|---|---|---|
| REVIEW | Web/PDF → evidence → tổng hợp và gợi ý gap → viết/kiểm | Literature review có phạm vi tìm nguồn, citations và limitations |
| EMPIRICAL | Method + CSV hợp lệ → routine được duyệt → metrics/charts → viết/kiểm | Bài thực nghiệm và gói tái lập |
| PROTOCOL | Đề xuất phương pháp/quy trình, review; chờ người dùng nếu cần | Protocol có hướng dẫn thu thập/phân tích; có thể resume khi nạp data |

Tổng quan/protocol áp dụng nhiều lĩnh vực; execution đầu tiên giới hạn một routine trên CSV numeric. Với lab/khảo sát/thực địa/người tham gia, con người thực hiện và xin phê duyệt phù hợp bên ngoài ATI. Thiếu actual data không tạo Results. Gợi ý gap chỉ dựa phạm vi nguồn đã xem; bản thảo hoàn chỉnh về cấu trúc không đồng nghĩa đã được peer review hoặc có novelty được công nhận.

**Mục tiêu bản nộp:** cả review web+PDF, một experiment chạy thật, protocol/wait/resume, Q&A/revision cơ bản, monitoring và đánh giá multi-agent. Tất cả là target cho tới khi có evidence nghiệm thu.

## 2. Problems and Objectives — Vấn đề và mục tiêu

| Vấn đề | Mục tiêu | Cách đánh giá |
|---|---|---|
| Tìm/đọc/đối chiếu nguồn tốn thời gian, dễ bỏ sót quan điểm | Phối hợp Researcher và Evidence Analyst | Coverage, evidence support, nguồn trái chiều trong tập đánh giá |
| LLM viết claim khó kiểm chứng | Lưu claim → evidence → nguồn/đoạn hoặc analysis artifact | Kiểm lineage toàn bài và chấm semantic support riêng |
| Research gap dễ bị khẳng định quá mức | Nêu search scope, uncertainty và giới hạn | Rubric kiểm claims về novelty và missing evidence |
| Bài thực nghiệm cần số liệu thật | Chạy routine hỗ trợ, tạo metrics/charts có manifest | Tái lập cùng input/config/seed; không fabricate Results |
| Workflow dài, có thể chờ nhiều ngày | Durable interrupt/resume, worker kết thúc khi chờ | Restart rồi resume đúng plan/checkpoint, không lặp outputs |
| Agent loop có thể tốn phí hoặc lặp vô hạn | 3 vòng thu thập gồm lần đầu; 2 writer revisions; shared budget | Cases no-delta, hết cap, retry và cancellation |
| User không thấy tiến độ hoặc không sửa được bài | Timeline, Q&A và report versions | Kịch bản thực tế và manual QA |
| Nhiều agent chưa chắc tốt hơn một agent | Đánh giá baseline và ablation | Cùng corpus/model/cap, báo quality/cost/latency và thất bại |

Không đưa tỷ lệ cải thiện, SLA hoặc chất lượng “production-ready” khi chưa đo. Citation tồn tại và quote khớp là integrity; mức độ bằng chứng hỗ trợ claim là đánh giá ngữ nghĩa riêng.

Yêu cầu chi tiết được đánh mã FR-01–FR-16 và NFR-01–NFR-07 trong [SRS](../requirements/SRS.md). Mã nghiệm thu G0–G7 ở SRS thống nhất với kế hoạch P0–P7; bảng ánh xạ giúp nhóm truy từ yêu cầu tới công việc và bằng chứng, tránh đánh dấu hoàn tất chỉ từ tài liệu.

## 3. Technical Approaches — Công nghệ, phương pháp và trade-offs

### 3.1 Phối hợp đa tác tử

| Vai trò | Trách nhiệm |
|---|---|
| Supervisor | Lập plan có version, phạm vi, đường nghiên cứu và budget |
| Researcher | Lập query, tìm nguồn và targeted search theo thiếu sót |
| Evidence Analyst | Trích claims/evidence, đối chiếu, synthesis và gợi ý gap |
| Methodologist | Đề xuất giả thuyết/phương pháp/protocol khi cần |
| Data Analyst | Chọn routine hỗ trợ và diễn giải kết quả thật |
| Writer | Viết đúng cấu trúc REVIEW/EMPIRICAL/PROTOCOL |
| Critic | Review toàn bài cùng evidence/method/results, trả issues/verdict |

REVIEW chủ yếu dùng năm vai trò; method/data roles có điều kiện. Curator/ingestion, router, validator, budget và runner là code/tools, không tính thêm agent. Critic không là peer reviewer độc lập. Research loop quay lại thu thập khi thiếu bằng chứng; revision loop sửa bài; guards quyết định có được đi tiếp.

### 3.2 Stack và đánh đổi

| Thành phần | Lựa chọn | Lý do / đánh đổi |
|---|---|---|
| UI/API | Next.js + FastAPI | Contract rõ, job dài tách HTTP; cần owner/version checks xuyên UI/API |
| Workflow | LangGraph trong Celery worker | Phù hợp state/loop/checkpoint; cần pin versions và xử lý side effect khi resume |
| Queue/events | Redis + DB outbox/TaskEvent | At-least-once delivery, dedup/CAS; Pub/Sub không là nguồn trạng thái duy nhất |
| Database | PostgreSQL + pgvector | Một DB giảm vận hành; pin embedding profile, lọc task và kiểm index |
| Providers | Search + safe fetch + LLM/embedding adapter | Shared call/cost/time cap, timeout/retry, data policy |
| Files | Private local ArtifactStore, interface mở rộng object storage | Owner/checksum/size/parser validation; file không public |
| Analysis | Trusted launcher + restricted Docker container | Routine dự án duyệt; API/worker không Docker socket; không là sandbox arbitrary code |
| Monitoring | JSON logs, AgentRun/TaskEvent, UI polling/SSE | Quan sát stage/usage/errors; không bắt thêm stack OTel cho bản nộp |

Kiến trúc dùng một backend codebase và các process API/worker, không tách mỗi agent thành microservice. Khái niệm container view theo [C4](https://c4model.com/diagrams/container); pause/resume theo [LangGraph](https://docs.langchain.com/oss/python/langgraph/interrupts); idempotency theo [Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html). Pin thư viện tương thích trước implementation.

Ma trận chi tiết chức năng–công nghệ–design pattern và ranh giới trust được nêu ở [Technical Design](../architecture/technical-design.md); HLD giải thích thành phần và trade-offs tại [System Architecture](../architecture/system-architecture.md).

### 3.3 Thực nghiệm và đánh giá

Routine tham chiếu `tabular_regression_v1`: CSV numeric → descriptive statistics → DummyRegressor(mean) so với Ridge(alpha=1), cùng train/test 80/20 seed 42. Preprocessing chỉ fit train; MAE chính, RMSE phụ; plots prediction/residual; không suy ra nhân quả, không thử lặp để chọn kết quả đẹp. Đây là lát cắt thực thi/tái lập, không phải thuật toán phù hợp mọi loại nghiên cứu. Nguyên tắc chống leakage tham khảo [scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html).

Đánh giá ATI khác với experiment của người dùng: 4 câu pilot và 8 held-out, ba cấu hình single-agent / multi-agent / multi-agent tắt macro loop; cố định corpus/model/cap, đo citation integrity, semantic support, coverage, cost/latency và failures. Vũ/My chấm ẩn nhãn, có phần chấm đôi; tập nhỏ nên không tuyên bố vượt trội phổ quát. [Evaluation Plan](evaluation-plan.md) ghi cách chọn mẫu và nghiệm thu.

## 4. System Design — Thiết kế hệ thống

Năm hình sau được đồng bộ từ [System Design](../architecture/system-design.md). Đây là target, không phải runtime đã nghiệm thu. Các nguyên tắc và giới hạn dưới mỗi hình trong nguồn chuẩn là một phần của thiết kế.

### 4.1 System Architecture — C4 Container View

```mermaid
flowchart TB
    User(["Người nghiên cứu"])

    subgraph ATI["ATI — Multi-Agent Research System"]
        UI["Web application<br/>Next.js · workspace và progress"]
        API["Application API<br/>FastAPI · auth · task · report · dispatcher"]
        Worker["Research worker<br/>Celery + LangGraph · agent workflow"]
        Redis[("Redis<br/>job broker · event notification")]
        DB[("PostgreSQL + pgvector<br/>state · evidence · checkpoints · events")]
        Files[("Private ArtifactStore<br/>PDF · CSV · charts · reports")]
        Launcher["Analysis launcher<br/>trusted operator process"]
        Runner["Analysis container<br/>approved routine · resource limits"]
    end

    subgraph Outside["Ngoài ranh giới ATI"]
        Search["Search provider"]
        Web["Public websites"]
        Models["LLM / embedding provider"]
        Human(["Lab / khảo sát / thực địa<br/>do con người thực hiện"])
    end

    User -->|"HTTPS"| UI
    UI <-->|"REST · progress SSE/polling"| API
    API -->|"ownership · state · outbox · event replay"| DB
    API -->|"authorized file access"| Files
    API <-->|"dispatch jobs · subscribe notifications"| Redis
    Redis <-->|"deliver jobs · publish notifications"| Worker
    Worker -->|"evidence · versions · checkpoints · events"| DB
    Worker -->|"read inputs · persist outputs"| Files
    Worker -->|"bounded manifest / result"| Launcher
    Launcher -->|"launch · supervise · collect"| Runner
    Worker -->|"queries / search results"| Search
    Worker -->|"safe fetch / page content"| Web
    Worker -->|"inference / embeddings"| Models
    User -.->|"uses reviewed protocol"| Human
    Human -.->|"data returned for upload"| User

    classDef app fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef store fill:#ecfdf5,stroke:#059669,color:#064e3b
    classDef execution fill:#fff7ed,stroke:#c2410c,color:#431407
    classDef external fill:#f8fafc,stroke:#94a3b8,color:#0f172a
    class UI,API,Worker app
    class DB,Files,Redis store
    class Launcher,Runner execution
    class Search,Web,Models,Human external
```

API dispatcher đọc outbox; Redis event chỉ là notification. Telemetry được lưu trong logs/DB và hiển thị ở UI, không bắt buộc service riêng. Analysis container chỉ chạy routine được duyệt qua launcher tin cậy.

### 4.2 Data Flow — Logical DFD Level 1

```mermaid
flowchart LR
    User(["Người nghiên cứu"])
    Sources(["Nguồn tài liệu bên ngoài"])

    P1["1.0 Quản lý yêu cầu<br/>và kế hoạch nghiên cứu"]
    P2["2.0 Thu thập, kiểm tra<br/>và chuẩn hóa nguồn"]
    P3["3.0 Phân tích bằng chứng<br/>và gợi ý khoảng trống"]
    P4["4.0 Thiết kế phương pháp<br/>và protocol"]
    P5["5.0 Phân tích dữ liệu<br/>bằng routine hỗ trợ"]
    P6["6.0 Viết, phản biện<br/>và cung cấp bài nghiên cứu"]

    D1[("D1 · Yêu cầu và kế hoạch")]
    D2[("D2 · Tài liệu và đoạn nguồn")]
    D3[("D3 · Nhận định và bằng chứng")]
    D4[("D4 · Dữ liệu và kết quả phân tích")]
    D5[("D5 · Phiên bản bài và phản hồi")]

    User -->|"câu hỏi · constraints · quyết định"| P1
    P1 -->|"kế hoạch và trạng thái"| User
    P1 -->|"yêu cầu đã duyệt"| D1
    D1 -->|"phạm vi tìm nguồn"| P2
    User -->|"PDF · CSV · kết quả được phép"| P2
    P2 -->|"truy vấn và địa chỉ nguồn"| Sources
    Sources -->|"metadata và nội dung"| P2
    P2 -->|"tài liệu đã chuẩn hóa"| D2
    P2 -->|"dataset hoặc kết quả có provenance"| D4
    D2 -->|"đoạn nguồn và định danh"| P3
    P3 -->|"claims · quotes · mâu thuẫn"| D3
    P3 -->|"tổng hợp · câu hỏi nghiên cứu"| P4
    D1 -->|"loại đầu ra và constraints"| P4
    P4 -->|"protocol và kế hoạch phân tích"| D1
    P4 -->|"cấu hình phân tích được hỗ trợ"| P5
    D4 -->|"dataset hợp lệ"| P5
    P5 -->|"metrics · charts · manifest"| D4
    P5 -->|"bằng chứng kết quả"| D3
    D1 -->|"scope · method · protocol"| P6
    D3 -->|"claims và evidence anchors"| P6
    D4 -->|"artifacts đã xác nhận"| P6
    D5 -->|"bài và phản hồi phiên bản trước"| P6
    User -->|"câu hỏi hoặc yêu cầu sửa bài"| P6
    P6 -->|"bài mới và kết quả kiểm tra"| D5
    P6 -->|"bài · protocol · câu trả lời có nguồn"| User
    P6 -->|"câu hỏi thiếu bằng chứng"| P2
    P6 -->|"đề xuất đổi scope hoặc phương pháp"| P1

    classDef process fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef data fill:#ecfdf5,stroke:#059669,color:#064e3b
    class P1,P2,P3,P4,P5,P6 process
    class D1,D2,D3,D4,D5 data
```

Mọi data store/external entity đi qua process; không đưa broker hoặc API vào logical view. Nghiên cứu bên ngoài trả dữ liệu cho người dùng, người dùng nạp qua process thu thập.

### 4.3 Inference Flow — Multi-Agent Workflow

```mermaid
flowchart TB
    Start(["Câu hỏi · nguồn riêng · loại đầu ra"])
    Plan["Supervisor<br/>lập plan có version và budget"]
    Approval{"Plan phù hợp policy<br/>và đã được duyệt?"}
    WaitPlan["WAITING_APPROVAL<br/>checkpoint · worker kết thúc"]
    Collect["Researcher + ingestion<br/>tìm, chuẩn hóa và index nguồn"]
    Evidence["Evidence Analyst<br/>claims · đối chiếu · gợi ý gap"]
    Path{"Đường nghiên cứu"}
    Method["Methodologist<br/>giả thuyết · method · protocol"]
    Execution{"Cần thực hiện bên ngoài?"}
    Protocol["Writer → Critic → Validator<br/>kiểm protocol trước bàn giao"]
    Continue{"Xuất protocol<br/>hay chờ dữ liệu?"}
    WaitData["WAITING_USER_DATA<br/>checkpoint · worker kết thúc"]
    DataGate{"Data và routine hợp lệ?"}
    Analysis["Data Analyst + isolated runner<br/>run thật · metrics · charts · manifest"]
    Draft["Writer<br/>bản nháp đúng loại và có provenance"]
    Critic["Critic<br/>toàn bài · evidence · method · results"]
    Verdict{"Verdict"}
    SearchGuard{"Còn vòng thu thập,<br/>evidence mới và budget?"}
    Target["Researcher<br/>tìm bổ sung theo issues"]
    RevisionGuard{"Còn lượt sửa<br/>và budget?"}
    Revise["Writer sửa theo issues<br/>tăng revision counter"]
    Validate{"Validator<br/>lineage và artifacts đạt?"}
    Limited["Kết thúc có giới hạn<br/>PARTIAL hoặc NEEDS_REVIEW"]
    Done(["COMPLETED<br/>bài đúng loại · artifacts · limitations"])

    Start --> Plan --> Approval
    Approval -->|"cần user"| WaitPlan
    WaitPlan -->|"decision đúng version · resume"| Plan
    Approval -->|"đạt"| Collect --> Evidence --> Path
    Path -->|"REVIEW"| Draft
    Path -->|"EMPIRICAL / PROTOCOL"| Method --> Execution
    Execution -->|"có / xuất PROTOCOL"| Protocol --> Continue
    Continue -->|"chỉ xuất · gate đạt"| Done
    Continue -->|"tiếp tục study"| WaitData
    Execution -->|"tính toán hỗ trợ"| DataGate
    DataGate -->|"thiếu hoặc chưa hỗ trợ"| WaitData
    WaitData -->|"upload READY · resume"| DataGate
    DataGate -->|"đạt"| Analysis
    Analysis -->|"run thành công · output hợp lệ"| Draft
    Analysis -->|"failed / timeout"| Limited
    Draft --> Critic --> Verdict
    Verdict -->|"đủ bằng chứng"| Validate
    Verdict -->|"thiếu evidence"| SearchGuard
    SearchGuard -->|"có"| Target --> Collect
    SearchGuard -->|"không"| Limited
    Verdict -->|"cần sửa bài"| RevisionGuard
    Verdict -->|"sai hoặc đổi method"| Plan
    RevisionGuard -->|"có"| Revise --> Critic
    RevisionGuard -->|"không"| Limited
    Validate -->|"đạt"| Done
    Validate -->|"cần sửa"| RevisionGuard

    classDef agent fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef gate fill:#fff7ed,stroke:#c2410c,color:#431407
    classDef wait fill:#f5f3ff,stroke:#7c3aed,color:#2e1065
    classDef terminal fill:#ecfdf5,stroke:#059669,color:#064e3b
    class Plan,Collect,Evidence,Method,Protocol,Analysis,Draft,Critic,Target,Revise agent
    class Approval,Path,Execution,Continue,DataGate,Verdict,SearchGuard,RevisionGuard,Validate gate
    class WaitPlan,WaitData wait
    class Done,Limited terminal
```

Budget guard bọc mọi provider call/retry ở tất cả node. Protocol dùng cùng Writer/Critic/Validator và caps. Plan approve không sinh lại plan; method change tạo version mới, không reset budget hay giữ Results cũ. Protocol chỉ được COMPLETED nếu đúng output user yêu cầu; thiếu dữ liệu empirical phải chờ hoặc user đổi output. PARTIAL cần lineage hợp lệ; lỗi chưa xử lý là NEEDS_REVIEW.

### 4.4 Asynchronous Sequence — Pause/Resume

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as Web UI
    participant API as API + outbox dispatcher
    participant DB as PostgreSQL
    participant Q as Redis broker/events
    participant W as Celery + LangGraph
    participant X as Provider / analysis adapter
    participant F as Private ArtifactStore

    U->>UI: Câu hỏi và lựa chọn output
    UI->>API: POST research (auth)
    API->>DB: Create owned task
    API-->>UI: 201 Created + task_id
    opt Nguồn hoặc dataset có sẵn
        UI->>API: Upload cho task
        API->>F: Validate/stage private file
        API->>DB: Artifact metadata + validation status
        API-->>UI: Artifact ID, chờ READY nếu parse async
    end
    UI->>API: Start + Idempotency-Key
    API->>DB: Transaction: run + QUEUED + outbox
    API-->>UI: 202 Accepted + run_id
    API->>Q: Background dispatcher publishes operation
    Q->>W: Deliver job (có thể lặp)
    W->>DB: Claim run/lease, dedup operation
    W->>X: Guarded plan call
    X-->>W: Versioned plan
    opt Assisted approval
        W->>DB: Checkpoint + WAITING_APPROVAL + event
        W-->>Q: Notify, job ends
        UI->>API: Approve/revise đúng plan_version
        API->>DB: Decision + resume outbox in transaction
        API->>Q: Dispatch resume
        Q->>W: New job, load checkpoint
    end
    W->>X: Guarded search/retrieval/analysis as applicable
    X-->>W: Evidence or verified artifacts
    opt Nghiên cứu cần dữ liệu người dùng
        W->>DB: Reviewed protocol + checkpoint + WAITING_USER_DATA
        W-->>Q: Notify, job ends
        API-->>UI: Progress snapshot / event, hướng dẫn upload
        Note over U,W: Không có Celery job sống trong thời gian làm lab/khảo sát
        U->>UI: Nạp kết quả được phép
        UI->>API: Upload, sau READY gửi resume
        API->>F: Validate + save private input
        API->>DB: Input/decision + resume outbox đúng version
        API->>Q: Dispatch resume
        Q->>W: New job, claim + load checkpoint
        W->>X: Supported routine / validate supplied-result provenance
        X-->>W: Actual output or needs-review reason
    end
    W->>DB: Writer/Critic/Validator results + report version + final event
    W-->>Q: Notify progress/final state
    Q-->>API: Notification hint
    API->>DB: Authorized event replay / snapshot
    API-->>UI: SSE / polling response
    UI->>API: Read report / download artifact
    API->>DB: Check owner and output validation status
    API->>F: Read authorized artifact
    API-->>UI: Report and artifacts
```

Tạo task trả 201, start/resume nhận job trả 202. WAITING_* giữ checkpoint và kết thúc worker; file READY + decision đúng owner/version mới được resume.

### 4.5 Core ERD — Traceability Model

```mermaid
erDiagram
    USER ||--o{ RESEARCH_TASK : owns
    RESEARCH_TASK ||--o{ RESEARCH_PLAN : versions
    RESEARCH_TASK ||--o{ RESEARCH_RUN : executes
    RESEARCH_PLAN |o--o{ RESEARCH_RUN : selected_by
    RESEARCH_TASK ||--o{ SOURCE : collects
    SOURCE ||--o{ DOCUMENT_CHUNK : contains
    RESEARCH_RUN ||--o{ RESEARCH_CLAIM : derives
    RESEARCH_CLAIM ||--o{ CLAIM_EVIDENCE : supported_or_challenged
    EVIDENCE ||--o{ CLAIM_EVIDENCE : anchors
    DOCUMENT_CHUNK |o--o{ EVIDENCE : document_anchor
    RESEARCH_ARTIFACT |o--o{ EVIDENCE : result_anchor
    RESEARCH_TASK ||--o{ RESEARCH_ARTIFACT : owns
    RESEARCH_RUN ||--o{ ANALYSIS_RUN : executes
    RESEARCH_ARTIFACT ||--o{ ANALYSIS_RUN : input_to
    ANALYSIS_RUN |o--o{ RESEARCH_ARTIFACT : produces
    RESEARCH_RUN ||--o{ RESEARCH_REPORT : creates
    RESEARCH_REPORT ||--o{ REPORT_CLAIM : includes
    RESEARCH_CLAIM ||--o{ REPORT_CLAIM : appears_in
    RESEARCH_REPORT ||--o{ CITATION : references
    RESEARCH_CLAIM |o--o{ CITATION : cited_for
    SOURCE ||--o{ CITATION : bibliographic_source
    DOCUMENT_CHUNK |o--o{ CITATION : optional_locator

    USER {
        uuid id PK
    }
    RESEARCH_TASK {
        uuid id PK
        uuid owner_id FK
    }
    RESEARCH_PLAN {
        uuid id PK
        uuid task_id FK
        int version
        string output_type
    }
    RESEARCH_RUN {
        uuid id PK
        uuid task_id FK
        uuid plan_id FK "nullable before planning"
        string status
    }
    SOURCE {
        uuid id PK
        uuid task_id FK
        string origin_locator
    }
    DOCUMENT_CHUNK {
        uuid id PK
        uuid source_id FK
        string content_hash
        string embedding_profile
    }
    RESEARCH_CLAIM {
        uuid id PK
        uuid run_id FK
        string statement
    }
    EVIDENCE {
        uuid id PK
        uuid chunk_id FK "nullable"
        uuid artifact_id FK "nullable"
        string locator
    }
    CLAIM_EVIDENCE {
        uuid claim_id PK,FK
        uuid evidence_id PK,FK
        string stance
    }
    RESEARCH_ARTIFACT {
        uuid id PK
        uuid task_id FK
        uuid producer_analysis_run_id FK "nullable"
        string kind
        string checksum
    }
    ANALYSIS_RUN {
        uuid id PK
        uuid research_run_id FK
        uuid input_artifact_id FK
        string routine_version
        string config_seed_manifest
    }
    RESEARCH_REPORT {
        uuid id PK
        uuid run_id FK
        int version
        string validation_status
    }
    REPORT_CLAIM {
        uuid report_id PK,FK
        uuid claim_id PK,FK
        string section_locator
    }
    CITATION {
        uuid id PK
        uuid report_id FK
        uuid source_id FK
        uuid chunk_id FK "nullable"
        uuid claim_id FK "nullable"
    }
```

Evidence neo đúng một chunk hoặc artifact; report → ReportClaim → claim → evidence → artifact → AnalysisRun → input là đường truy xuất kết quả. Citation vẫn là thư mục source/chunk. FK kiểm quan hệ kỹ thuật, không chứng minh nội dung claim đúng. Mọi link phải cùng task/owner; uploaded artifact có producer nullable. Physical DFD/class view và invariants đầy đủ ở [System Design phụ lục](../architecture/system-design.md).

## 5. Development Plan — Kế hoạch phát triển

Thời hạn 10/09–10/11/2026. Giai đoạn đầu đã có planning/scaffold và baseline log 27/09. Lịch còn lại tính từ 08/10, giả định Chiến có 3–4 giờ tập trung/ngày; cần điều chỉnh theo velocity thực tế sau baseline.

| Thời gian | Công việc | Người phụ trách | Gate/đầu ra |
|---|---|---|---|
| 08–10/10 | P0 baseline/dependency/DB/test isolation | Chiến | G0: tái lập môi trường |
| 11–14/10 | P1 auth/ownership/run/outbox/events | Chiến | G1: lifecycle và quyền |
| 15–19/10 | P2 web E2E/evidence/critic/validator/budget | Chiến; My/Vũ review nội dung | G2: review chạy thật |
| 20–23/10 | P3 PDF/workspace/progress | Chiến; Hiếu scenarios | G3: web+PDF |
| 24–26/10 | P4 plan/protocol/wait/resume | Chiến | G4: durable resume |
| 27–30/10 | P5 routine/metrics/charts/empirical | Chiến; Vũ dataset trước 16/10 | G5: experiment thật và tái lập |
| 31/10–02/11 | P6 Q&A/revision/export và delete/cleanup | Chiến | G6: phiên bản, đầu ra và retention |
| 03–07/11 | P7 evaluation/manual QA/fix/báo cáo | Cả nhóm theo vai trò | G7: kết quả có evidence |
| 08–10/11 | Buffer/freeze/demo/backup | Cả nhóm | Bản nộp |

Chi tiết ước lượng 83–108 giờ trong [Implementation Plan](implementation-plan.md). Đây là kế hoạch rủi ro cao do một developer và nhiều phần chưa chạy. Cắt polish/ảnh/PDF đẹp khi trễ; không bỏ số liệu thật/provenance/ownership rồi báo đủ scope.

Report version/ReportClaim và plan schema được đặt nền ở P2; P4 mở approval/resume, P6 mở Q&A/revision. WAITING_* giữ active run nhưng trả worker; Q&A đọc phiên bản bài qua operation có cap riêng. Mọi trường hợp xóa task phải chặn truy cập/resume và kết quả đến muộn theo policy đã ghi trong SRS.

## 6. Progress — Tiến độ có bằng chứng

| Hạng mục | Bằng chứng hiện có | Chưa được xác nhận |
|---|---|---|
| Planning | SRS v4.0, ADR-004, diagrams, implementation/evaluation plans cập nhật 08/10 | Feature chưa hoàn tất chỉ vì đã mô tả |
| Docker/DB/API/worker/graph | Baseline chạy 27/09: services, health/task smoke, worker ping, graph compile/routing mẫu | Revision hiện tại, clean DB migration, research provider E2E |
| Auth/provenance schema | Source `ebb525a` có register và ClaimEvidence/Citation migration | Login/ownership, migration áp dụng, validator thật |
| Research workflow | Có search/fetch/embed/retrieval/Writer/Critic source | Đủ budget/lineage/review/loop và chất lượng thực tế |
| Upload/resume/analysis/Q&A | Có thiết kế và backlog | Chưa đủ runtime evidence |
| Monitoring/evaluation | Kế hoạch event/log/timeline và baseline/ablation | Chưa có số đo chất lượng/cost/superiority |

[Baseline Verification](baseline-verification.md) giữ nguyên lệnh/kết quả lịch sử. Đọc source ngày 08/10 không chứng minh deployment hiện tại đã chạy. Lượt chốt planning này không gọi provider hoặc chạy experiment.

## 7. AI Disclosure — Đóng góp con người và AI

| Thành phần | Trách nhiệm / hỗ trợ | Trạng thái khai báo |
|---|---|---|
| Nguyễn Đình Chiến | Chủ trách nhiệm kế hoạch, quyết định scope/architecture, implementation/tích hợp và nghiệm thu | Có AI hỗ trợ code/tài liệu; không diễn đạt thành mọi dòng code đều tự viết |
| Phạm Long Vũ | Dataset/query/rubric và QA/chấm nội dung | Phân công; cập nhật bàn giao thực tế |
| Nguyễn Văn Hiếu | Scenarios/flow/checklist/issue log | Phân công; cập nhật bàn giao thực tế |
| Nguyễn Thị Hải My | Related work/nguồn, chấm và biên tập | Phân công; cập nhật bàn giao thực tế |
| Gemini / Antigravity | Theo thông tin chủ dự án: hỗ trợ drafts/code/docs và workflow review | Gắn task/commit/model thực tế trước nộp; không suy đoán mức đóng góp |
| Codex | Hỗ trợ đọc source/docs, rà kiến trúc, đề xuất/chỉnh planning và diagrams; các lượt trước có hỗ trợ code/baseline | Lượt 08/10 là rà soát/planning, không nghiệm thu runtime; Chiến review quyết định cuối |

AI của sản phẩm ATI khác với AI giúp nhóm phát triển. Không tự điền tỷ lệ AI/con người hoặc model version chưa xác minh. Người làm chịu trách nhiệm nguồn, số liệu, code và kết luận. Hồ sơ chi tiết ở [AI Disclosure](ai-disclosure.md).

## 8. Tài liệu kèm theo và tham khảo

- [SRS](../requirements/SRS.md), [HLD](../architecture/system-architecture.md), [ADR-004](../architecture/decisions/ADR-004-multi-agent-research-delivery.md).
- [Product Assessment](product-assessment.md), [Implementation Plan](implementation-plan.md), [Evaluation Plan](evaluation-plan.md), [Team Task Guide](team-task-guide.md).
- [GPT Researcher](https://github.com/assafelovic/gpt-researcher): tham khảo thu thập nguồn và báo cáo.
- [STORM](https://github.com/stanford-oval/storm): tham khảo lập câu hỏi nhiều góc nhìn và tổ chức tri thức.
- [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2): tham khảo chu trình thực nghiệm/bài viết; không đồng nhất scope rộng của ATI với khả năng tự nghiên cứu mọi lĩnh vực.
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): tham khảo thiết kế workflow có cấu trúc, đánh giá trade-offs; không là bằng chứng ATI tốt hơn baseline.

MSSV, giảng viên, ngày nộp, bàn giao cá nhân và progress thực tế còn phải điền từ thông tin nhóm; không tạo dữ liệu giả.
