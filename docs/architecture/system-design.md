# System Design — Multi-Agent Research System (ATI)

## 1. Phạm vi và nguyên tắc

**Cập nhật thiết kế: 09/10/2026.** Đây là nguồn chuẩn cho sơ đồ mục tiêu; không mô tả mọi tính năng đã chạy. [SRS v4.1](../requirements/SRS.md) chốt yêu cầu; [ADR-004](decisions/ADR-004-multi-agent-research-delivery.md) giải thích quyết định; mục 9 tách hiện trạng.

ATI phối hợp agent để tạo bài báo có bằng chứng và thực nghiệm tái lập. Ba đường REVIEW / EMPIRICAL_COMPUTATIONAL / EMPIRICAL_HUMAN dùng chung provenance và review; **mỗi bài có workspace, run, checkpoint và phiên bản riêng**. Protocol là artifact trung gian của đường human-led, không phải bài báo đã hoàn thành. Execution tự động chỉ cho routine hỗ trợ. Không có dữ liệu thật thì không tạo Results. Gợi ý khoảng trống nghiên cứu phải nêu phạm vi nguồn đã xem; Critic không thay peer review.

Năm hình chính đáp ứng kiến trúc, data flow, inference, tương tác bất đồng bộ và mô hình dữ liệu. Hai phụ lục phục vụ kỹ thuật. Mermaid dùng notation dễ đọc; Logical DFD là biểu diễn logic, không tuyên bố đúng toàn bộ hình dạng Gane–Sarson. Hình kiến trúc thể hiện process/data boundary; agent là logic bên trong worker.

## 2. System Architecture — C4 Container View

Một kiến trúc hoàn chỉnh với các dependency chính. Mũi tên tới provider/storage biểu diễn lời gọi và dữ liệu trả về theo giao thức đó; không vẽ thêm từng response để tránh giao cắt.

```mermaid
flowchart TB
    User(["Người nghiên cứu"])

    subgraph ATI["ATI — Multi-Agent Research System"]
        UI["Web application<br/>Next.js · danh sách bài, workspace và progress"]
        API["Application API<br/>FastAPI · auth · task · report · dispatcher"]
        Worker["Research worker<br/>Celery + LangGraph · agent workflow"]
        Redis[("Redis<br/>job broker · event notification")]
        DB[("PostgreSQL + pgvector<br/>tasks/runs · evidence · checkpoints · events")]
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

- API/worker dùng chung codebase. Outbox dispatcher là background task của API, có DB claim/lease nếu nhiều replica.
- Telemetry là JSON logs + AgentRun/TaskEvent + UI timeline, xuyên API/worker/launcher; không bắt buộc một service mới. Monitoring không hiển thị suy luận nội bộ.
- Runner staging input/output riêng theo job; launcher kiểm manifest và thu artifacts. API/worker **không có Docker socket**. Container chỉ chạy routine tin cậy, không là sandbox cho mã đối kháng.
- File storage private local volume cho bản nộp, có interface đổi S3-compatible sau. Ảnh minh họa tùy chọn dùng source page trước; provider Serper có thể bổ sung qua adapter theo ADR-001, không phải dependency bắt buộc.
- Không tách phase/release trong hình; phạm vi triển khai được quản lý ở kế hoạch.
- Một user có nhiều task độc lập. Task đang chờ dữ liệu không giữ worker và không khóa task khác; quota chạy đồng thời kiểm ở dispatcher, không dùng Redis làm nơi lưu checkpoint.

## 3. Logical Data Flow — DFD Level 1

Tập trung dữ liệu nghiệp vụ; hạ tầng được tách sang Physical DFD. Mọi external entity/data store trao đổi qua process. Lab/thực địa trả dữ liệu cho người dùng rồi được nạp vào ATI.

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
    P6 -->|"bài báo đầy đủ · protocol trung gian · câu trả lời có nguồn"| User
    P6 -->|"câu hỏi thiếu bằng chứng"| P2
    P6 -->|"đề xuất đổi scope hoặc phương pháp"| P1

    classDef process fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef data fill:#ecfdf5,stroke:#059669,color:#064e3b
    class P1,P2,P3,P4,P5,P6 process
    class D1,D2,D3,D4,D5 data
```

P5 chỉ chạy routine được hỗ trợ; dữ liệu/kết quả human-led đã nạp vẫn đi từ D4 qua kiểm provenance tới P6, không gắn nhãn ATI đã chạy nếu ATI không phân tích lại. P6 có thể cung cấp REVIEW không qua thí nghiệm hoặc cung cấp **protocol trung gian** khi đang chờ; chỉ bài đáp ứng gate theo loại mới là đầu ra `COMPLETED`. DFD không biểu diễn điều kiện điều khiển hay mọi provider call; xem inference và physical view.

## 4. Inference Flow — Multi-Agent Workflow

Flowchart mô tả điều khiển ở độ chi tiết vừa đủ. **Mọi provider call** ở tất cả node (kể cả plan, targeted search, revision và retry) qua cùng budget adapter; không lặp nhiều đường nét đứt budget gây rối.

```mermaid
flowchart TB
    Start(["Câu hỏi · nguồn riêng · bài muốn viết"])
    Plan["Supervisor<br/>lập plan có version và budget"]
    Approval{"Plan phù hợp policy<br/>và đã được duyệt?"}
    WaitPlan["WAITING_APPROVAL<br/>checkpoint · worker kết thúc"]
    Collect["Researcher + ingestion<br/>tìm, chuẩn hóa và index nguồn"]
    Evidence["Evidence Analyst<br/>claims · đối chiếu · gợi ý gap"]
    Path{"Đường nghiên cứu"}
    Method["Methodologist<br/>giả thuyết · method · protocol"]
    DataGate{"Dữ liệu/kết quả thật<br/>đủ và hợp lệ?"}
    Protocol["Methodologist + Writer/Critic<br/>protocol và biểu mẫu trung gian"]
    WaitData["WAITING_USER_DATA<br/>checkpoint · worker kết thúc"]
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
    Done(["COMPLETED<br/>bài báo đủ phần · nguồn · Results thật nếu cần"])

    Start --> Plan --> Approval
    Approval -->|"cần user"| WaitPlan
    WaitPlan -->|"decision đúng version · resume"| Plan
    Approval -->|"đạt"| Collect --> Evidence --> Path
    Path -->|"REVIEW"| Draft
    Path -->|"EMPIRICAL_COMPUTATIONAL / EMPIRICAL_HUMAN"| Method --> DataGate
    DataGate -->|"cần lab / khảo sát / thực địa"| Protocol --> WaitData
    DataGate -->|"thiếu CSV hoặc kết quả"| WaitData
    WaitData -->|"upload READY · resume"| DataGate
    DataGate -->|"CSV + routine được hỗ trợ"| Analysis
    DataGate -->|"kết quả human-led có provenance"| Draft
    Analysis -->|"run thành công · output hợp lệ"| Draft
    Analysis -->|"failed / timeout sau retry"| Limited
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
    class Approval,Path,DataGate,Verdict,SearchGuard,RevisionGuard,Validate gate
    class WaitPlan,WaitData wait
    class Done,Limited terminal
```

**Quy tắc đọc hình:**

- Assisted cần user duyệt; Automatic chỉ duyệt trong policy/cap đã cấp. Approve giữ plan version, revise tạo version mới; node Plan kiểm decision hiện hữu, không sinh lại plan sau approve.
- Thu thập tối đa 3 rounds tính cả lần đầu; có thể dừng sớm khi no-evidence-delta. Writer tối đa 2 revisions sau draft đầu, citation repair dùng chung counter. Protocol là bản hướng dẫn đã review để người dùng thực hiện bên ngoài; không đi thẳng tới Done.
- Method change tạo plan version, kiểm lại policy và hủy hiệu lực Results cũ. Các lượt này vẫn chịu active-time/call/cost cap, không reset budget.
- WaitData không tự chạy bất kỳ file nào; upload/resume phải qua owner, READY, checkpoint/plan version và idempotency checks. Dataset hoặc routine chưa hỗ trợ phải hướng dẫn sửa dữ liệu/đổi method hợp lệ; không chuyển ngầm thành bài khác. Results do người dùng cung cấp phải được kiểm provenance và ghi nhãn; không tự báo đã tái lập. Thất bại runner được retry hữu hạn theo cùng manifest, sau đó chờ can thiệp hoặc thành NEEDS_REVIEW; không tạo Results giả.
- PARTIAL chỉ được phát hành khi lineage của phần giữ lại hợp lệ; lỗi lineage/method chưa giải quyết là NEEDS_REVIEW. Mọi node có thể kết thúc FAILED/CANCELLED; không vẽ lặp các nhánh này.
- Với bài human-led, Writer chỉ viết Results sau khi có dữ liệu/kết quả thực và metadata phương pháp đủ dùng; nếu cần suy luận định lượng nhưng routine không hỗ trợ, yêu cầu người dùng cung cấp kết quả phân tích có provenance hoặc thay phương pháp. `COMPLETED` luôn là bài báo đủ phần theo loại, không phải protocol.

## 5. Asynchronous Sequence — Hai bài độc lập, pause và resume

Tách tạo workspace (201 Created) và nhận job (202 Accepted). Ví dụ task A cần nghiên cứu ngoài hệ thống, còn task B là review; hai task giữ run/checkpoint/artifacts riêng. Không giữ worker trong thời gian chờ người dùng. Đây là contract target; route hiện tại còn trả 200 khi start.

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

    U->>UI: Tạo bài A, chọn nghiên cứu ngoài hệ thống
    UI->>API: POST tasks (auth)
    API->>DB: Tạo task A có owner
    API-->>UI: 201 Created + task_id A
    UI->>API: POST A/start + Idempotency-Key
    API->>DB: Run A QUEUED + outbox trong transaction
    API-->>UI: 202 Accepted + run_id A
    UI->>API: GET A/events (SSE) hoặc polling snapshot
    API->>Q: Dispatch khi có suất chạy
    Q->>W: Deliver A
    W->>DB: Claim A, lưu plan và evidence/events
    W->>X: Các agent tìm nguồn và kiểm protocol
    X-->>W: Evidence + reviewed protocol
    W->>F: Lưu protocol, biểu mẫu và bản nháp A
    W->>DB: Checkpoint A + WAITING_USER_DATA + event
    W-->>Q: Kết thúc job, trả worker lease
    API-->>UI: Snapshot / SSE: A chờ dữ liệu, có protocol để tải
    Note over U,W: Không có job A sống trong thời gian lab / khảo sát
    U->>UI: Tạo bài B trong lúc A chờ
    UI->>API: POST tasks (bài B)
    API->>DB: Tạo task B có owner
    API-->>UI: 201 Created + task_id B
    UI->>API: POST B/start + Idempotency-Key
    API->>DB: Run B QUEUED + outbox độc lập
    API-->>UI: 202 Accepted + run_id B
    UI->>API: GET B/events (SSE) hoặc polling snapshot
    API->>Q: Dispatch B theo quota/fairness
    Q->>W: Deliver B
    W->>DB: Research B, report version, COMPLETED
    API-->>UI: Bài báo B sẵn sàng, A vẫn WAITING_USER_DATA
    U->>UI: Quay lại A, tải dữ liệu/kết quả thực lên
    UI->>API: POST A/artifacts
    API->>F: Validate và lưu file riêng của A
    API->>DB: Artifact A chuyển READY sau xử lý
    API-->>UI: Artifact ID và trạng thái READY
    UI->>API: POST A/resume với plan/checkpoint version
    API->>DB: Kiểm owner/READY/version, QUEUED + outbox A
    API-->>UI: 202 Accepted, A QUEUED nếu hết suất
    API->>Q: Dispatch A khi có suất
    Q->>W: Claim A, load checkpoint A
    W->>X: Kiểm provenance / phân tích routine hỗ trợ
    X-->>W: Kết quả thật hoặc lý do cần bổ sung
    alt Đủ bằng chứng và Results thật
        W->>DB: Writer/Critic/Validator + report A version + COMPLETED
        API-->>UI: Bài báo A có thể đọc, hỏi, sửa và xuất
    else Thiếu hoặc lỗi dữ liệu
        W->>DB: WAITING_USER_DATA / NEEDS_REVIEW + lý do
        API-->>UI: Việc cần làm, bài báo chưa hoàn thành
    end
    UI->>API: Xem bài/tiến độ/tải artifact theo task_id
    API->>DB: Kiểm owner + replay event/snapshot
    API->>F: Đọc file riêng được phép
    API-->>UI: Report/protocol/manifest tương ứng task
```

Provider error, cancellation và redelivery được xử lý bằng transition/idempotency guards ở mỗi bước; không chỉ dựa Celery acknowledgement. File phải READY trước resume. Quota chạy đồng thời chỉ giới hạn job RUNNING; QUEUED bền vững có thể đợi, WAITING_* không chiếm suất. Notification không thay DB event; mất Pub/Sub vẫn khôi phục tiến độ từ DB.

## 6. Core ERD — Target Traceability Model

Chỉ vẽ trục dữ liệu nghiên cứu. Auth sessions, outbox, TaskEvent, AgentRun và checkpointer tables được mô tả trong [Data Model and API](../technical/data-model-and-api.md).

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
        string article_type
        string status
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
        string validation_status
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
        string article_type
        string validation_status
        string completeness_status
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

**Invariants cần triển khai ngoài hình:**

1. Evidence neo **đúng một** chunk hoặc artifact; mọi liên kết cùng task/owner. Đoạn quote/locator phải khớp nguồn; FK không chứng minh claim đúng về ngữ nghĩa.
2. Upload artifact có producer nullable; output phân tích có producer_analysis_run_id và input/config/hash/version truy xuất được. Một AnalysisRun hiện dùng một CSV đầu vào; mở nhiều input cần junction sau.
3. Citation là thư mục tài liệu. Kết quả thực nghiệm trace qua ReportClaim → ClaimEvidence → Evidence → Artifact → AnalysisRun → input. Không bắt artifact giả làm Source hoặc citation thư mục.
4. Report version unique trong task; plan version unique trong task. Claim có thể được tái dùng trong version cùng task nhưng phải giữ nguyên provenance. Citation gắn claim phải xuất hiện trong ReportClaim tương ứng.
5. Một active ResearchRun/task, nhiều task/user; WAITING_* chỉ khóa run của chính task, không giữ worker hoặc quota RUNNING. plan_id nullable trước khi Supervisor tạo plan, bắt buộc có trước research execution; khi revise plan trong run, cập nhật selected plan bằng CAS, giữ audit/version cũ. Delete/tombstone không được để resume tiếp tục.
6. Hình lược bỏ field vận hành; migration phải bổ sung composite keys/check constraints theo [data contract](../technical/data-model-and-api.md), không suy diễn schema hiện tại đã có chúng.

## 7. Phụ lục — Physical DFD

Bổ sung góc nhìn dữ liệu đi qua công nghệ triển khai, không thay Logical DFD.

```mermaid
flowchart LR
    Browser["Browser / Next.js"]
    API["FastAPI<br/>authorization · dispatcher"]
    DB[("PostgreSQL + pgvector")]
    Files[("Private file storage")]
    Redis[("Redis")]
    Worker["Celery / LangGraph"]
    Providers["Search / web / LLM"]
    Analysis["Analysis adapter<br/>trusted launcher → restricted container"]

    Browser -->|"request · upload · decision"| API
    API -->|"task/run · outbox · artifact metadata"| DB
    DB -->|"snapshot · event history · ownership"| API
    API -->|"validated file bytes"| Files
    Files -->|"authorized bytes"| API
    API -->|"response · progress · download"| Browser
    API -->|"operation payload"| Redis
    Redis -->|"job delivery"| Worker
    Worker -->|"state · evidence · reports · events"| DB
    DB -->|"checkpoint · plan · retrieval"| Worker
    Worker -->|"provider requests"| Providers
    Providers -->|"content · model output"| Worker
    Worker -->|"routine ID · staged input manifest"| Analysis
    Analysis -->|"metrics · charts · execution manifest"| Worker
    Files -->|"input files"| Worker
    Worker -->|"output artifacts"| Files
    Worker -->|"event notification"| Redis
    Redis -->|"notification hint"| API

    classDef app fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef data fill:#ecfdf5,stroke:#059669,color:#064e3b
    class Browser,API,Worker,Analysis,Providers app
    class DB,Files,Redis data
```

Lab/khảo sát/thực địa không thuộc runtime ATI; người dùng nạp dữ liệu qua API có kiểm tra rồi API lưu private storage. Analysis node gom adapter/launcher/container trong góc nhìn dòng dữ liệu; ranh giới execution tách tại hình kiến trúc. Các bước validate/checkpoint là logic target, không phải bằng chứng đã triển khai.

## 8. Phụ lục — Conceptual Class Diagram

Interface logic phục vụ triển khai; không ánh xạ mỗi class thành agent hoặc service.

```mermaid
classDiagram
    class ResearchService {
        +createTask()
        +startRun()
        +resumeRun()
        +reviseReport()
    }
    class ResearchWorkflow {
        +invoke()
        +interrupt()
        +resume()
    }
    class AgentRole {
        <<interface>>
        +execute(context) StructuredOutput
    }
    class BudgetManager {
        +reserve()
        +reconcile()
    }
    class EvidenceRepository {
        +saveAnchoredEvidence()
        +retrieveForTask()
    }
    class OutputValidator {
        +validateLineage()
        +validateArtifacts()
    }
    class AnalysisAdapter {
        <<interface>>
        +runApprovedRoutine(manifest)
    }
    class ArtifactStore {
        <<interface>>
        +putPrivate()
        +getAuthorized()
    }
    class RunRepository {
        +claimOperation()
        +saveEvent()
        +saveCheckpointReference()
    }
    ResearchService --> RunRepository
    ResearchService --> ArtifactStore
    ResearchService ..> ResearchWorkflow : dispatches via outbox
    ResearchWorkflow --> AgentRole
    ResearchWorkflow --> BudgetManager
    ResearchWorkflow --> EvidenceRepository
    ResearchWorkflow --> OutputValidator
    ResearchWorkflow --> AnalysisAdapter
    ResearchWorkflow --> RunRepository
    AnalysisAdapter --> ArtifactStore : stages validated inputs and outputs
```

Bảy role implement cùng contract nhưng có input/output schema riêng. Validator không phải LLM role; semantic review thuộc Critic và đánh giá con người. Worker gọi analysis adapter, không được thực thi shell do model tạo.

## 9. Hiện trạng và khoảng cách

Đọc source `ebb525a` ngày 08/10: API/task/graph/tools và một phần provenance schema có; register đã có nhưng research routes còn dummy user. Budget guard, citation validation thật, ownership, durable waits, run/report versioning, upload/runner và đánh giá multi-agent chưa có đủ bằng chứng hoạt động.

Lần runtime gần nhất được ghi lại là 27/09, không xác minh các thay đổi sau đó. Xem [Product Assessment](../project/product-assessment.md) cho findings và [Implementation Plan](../project/implementation-plan.md) cho gates. Không ghi feature hoàn thành từ sơ đồ/đọc code.

## 10. Tài liệu tham khảo

- [C4 Model — Container diagram](https://c4model.com/diagrams/container): ranh giới application/data store.
- [IBM — Data flow diagram](https://www.ibm.com/think/topics/data-flow-diagram): phân biệt logical/physical data flow.
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): checkpoint và resume; side effect phải idempotent.
- [Celery — Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html): delivery/acknowledgement và idempotency.
- [Docker — Security](https://docs.docker.com/engine/security/): giới hạn và ranh giới container.
