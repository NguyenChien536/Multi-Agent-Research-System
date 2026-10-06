# System Design — Multi-Agent Research System (ATI)

## 1. Phạm vi và nguyên tắc

Đây là **nguồn chuẩn cho các sơ đồ kiến trúc mục tiêu** của ATI. Sơ đồ mô tả đích thiết kế, không khẳng định prototype đã có đủ chức năng; bằng chứng triển khai được ghi riêng ở mục 9 và [baseline-verification.md](../project/baseline-verification.md).

ATI điều phối quy trình nghiên cứu có AI hỗ trợ và con người giám sát: từ câu hỏi, tổng quan nguồn, candidate research question/gap, giả thuyết hoặc hướng nghiên cứu, phương pháp/protocol đến phân tích dữ liệu phù hợp và bản thảo bài báo theo loại nghiên cứu. Người dùng có thể đưa tài liệu của họ vào. Phần kết quả thực nghiệm chỉ được viết khi có dữ liệu thật và provenance. Với nghiên cứu cần lab, khảo sát, thực địa hoặc người tham gia, ATI tạo protocol/hướng dẫn; con người xin review cần thiết, tự thực hiện và nạp kết quả được phép xử lý.

**Các nguyên tắc xuyên suốt:**

- Candidate gap chỉ phản ánh những gì chưa rõ trong tập nguồn và phạm vi tìm kiếm đã báo cáo; không tuyên bố là khoảng trống tuyệt đối của cả lĩnh vực.
- Không tạo số liệu hoặc phần Results giả. Thiếu dữ liệu thì xuất literature review, protocol hoặc draft đánh dấu phần chưa hoàn tất.
- Chỉ chạy các routine phân tích có hỗ trợ, schema và cấu hình rõ. Không chạy mã tùy ý do LLM tạo trong API/worker. Runner phải tách biệt, có giới hạn tài nguyên và network mặc định bị chặn.
- Nghiên cứu người tham gia chỉ được hỗ trợ soạn protocol/tài liệu mẫu và hướng dẫn xin phê duyệt phù hợp. ATI không tuyển người, xin consent thay nhóm nghiên cứu, hay khởi động nghiên cứu ngoài đời.
- Macro research loop và micro revision loop đều bị giới hạn; Critic không thay thế peer review. Citation validation kiểm tra lineage, không chứng minh claim đúng về ngữ nghĩa.
- Ảnh minh họa là tùy chọn, lấy từ trang đã thu thập trước hoặc image provider đã cấu hình; người dùng có thể bỏ ảnh/tắt ảnh. Ảnh không phải evidence.

| Ký hiệu | Ý nghĩa |
|---|---|
| Hình chữ nhật / process | Container hoặc xử lý nghiệp vụ |
| Hình trụ | Kho dữ liệu |
| Nút bo tròn | Tác nhân, điểm đầu/cuối |
| Hình thoi | Quyết định / guard |
| Mũi tên nét đứt | Event hoặc luồng tùy chọn |

## 2. System Architecture — C4 Container View

Cho thấy các container chính và ranh giới với provider ngoài. LangGraph và các agent là logic bên trong worker; isolated runner là ranh giới riêng cho phân tích dữ liệu.

```mermaid
flowchart TB
    User(["Researcher / Student"])

    subgraph ATI["ATI — Research Orchestration System"]
        UI["Web UI<br/>Next.js"]
        API["Application API<br/>FastAPI · auth · tasks · review · reports"]
        Redis[("Redis<br/>job queue · progress events")]
        Worker["Research Worker<br/>Celery + LangGraph"]
        DB[("PostgreSQL + pgvector<br/>tasks · plans · sources · evidence · reports")]
        Files[("Object Storage<br/>uploaded files · datasets · exports")]
        Runner["Isolated Analysis Runner<br/>approved routines only"]
        Observe["Observability<br/>structured logs · metrics · traces"]
    end

    subgraph External["External services and human-led work"]
        Search["Search Provider<br/>Tavily / configured provider"]
        Web(["Public websites"])
        LLM["LLM + Embedding Provider"]
        Image["Optional image-search provider"]
        HumanStudy(["Lab / survey / field work<br/>outside ATI"])
    end

    User -->|"HTTPS"| UI
    UI -->|"REST / JSON"| API
    API -.->|"SSE progress events"| UI
    API -->|"authorize · read/write"| DB
    API -->|"authorized upload/download"| Files
    API -->|"enqueue or resume job"| Redis
    Redis -->|"deliver job"| Worker
    Worker -->|"state · evidence · report metadata"| DB
    Worker -->|"read input · save artifacts"| Files
    Worker -->|"bounded analysis request"| Runner
    Runner -->|"tables · statistics · chart artifacts"| Worker
    Worker -->|"search query"| Search
    Search -->|"URLs and snippets"| Worker
    Worker -->|"fetch public page"| Web
    Web -->|"page content"| Worker
    Worker -->|"inference / embeddings"| LLM
    Worker -.->|"optional image query"| Image
    Worker -->|"logs · metrics · traces"| Observe
    API -->|"request telemetry"| Observe
    User -.->|"uses exported protocol outside ATI"| HumanStudy
    HumanStudy -.->|"results return to researcher"| User

    classDef user fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
    classDef app fill:#eff6ff,stroke:#2563eb,stroke-width:1.5px,color:#172554
    classDef queue fill:#fff7ed,stroke:#ea580c,stroke-width:1.5px,color:#431407
    classDef data fill:#ecfdf5,stroke:#059669,stroke-width:1.5px,color:#022c22
    classDef control fill:#f5f3ff,stroke:#7c3aed,stroke-width:1.5px,color:#2e1065
    classDef external fill:#f8fafc,stroke:#94a3b8,stroke-width:1.5px,stroke-dasharray:5 4,color:#0f172a

    class User,HumanStudy user
    class UI,API,Worker app
    class Redis queue
    class DB,Files data
    class Runner,Observe control
    class Search,Web,LLM,Image external
```

**Lưu ý:** Công nghệ cụ thể cho runner chưa được chốt; cần ADR và threat model trước khi xử lý dữ liệu/mã không tin cậy. Observability thể hiện năng lực mục tiêu, chưa có nghĩa đã cấu hình OTel/dashboard.

## 3. Logical Data Flow — DFD Level 1

DFD này chỉ biểu diễn dữ liệu và process nghiệp vụ, không đưa UI, API, Redis hoặc Celery vào.

```mermaid
flowchart LR
    Researcher(["Researcher"])
    Search(["Search provider"])
    Web(["Public websites"])
    Model(["LLM / embedding provider"])

    P1["1.0<br/>Define question,<br/>scope and plan"]
    P2["2.0<br/>Discover, upload<br/>and curate sources"]
    P3["3.0<br/>Synthesize evidence<br/>and candidate questions"]
    P4["4.0<br/>Design method,<br/>hypothesis and protocol"]
    P5["5.0<br/>Analyze supported data<br/>or receive human results"]
    P6["6.0<br/>Write, critique<br/>and validate article"]

    D1[("D1 · Tasks, plans,<br/>checkpoints")]
    D2[("D2 · Sources, chunks,<br/>vectors")]
    D3[("D3 · Claims, evidence,<br/>provenance")]
    D4[("D4 · Input data, protocols,<br/>analysis artifacts")]
    D5[("D5 · Article versions,<br/>citations, exports")]

    Researcher -->|"Question · scope · study type"| P1
    P1 -->|"Plan · status"| Researcher
    P1 <-->|"Task and plan state"| D1
    P1 -->|"Search/source requirements"| P2
    Researcher -->|"Uploaded papers / permitted data"| P2
    P2 -->|"Search query"| Search
    Search -->|"Candidate URLs"| P2
    P2 -->|"Fetch request"| Web
    Web -->|"Page/document content"| P2
    P2 -->|"Curated sources"| D2
    P2 -->|"Text for embeddings"| Model
    Model -->|"Vectors"| P2
    D2 -->|"Sources and passages"| P3
    P3 -->|"Synthesis/extraction request"| Model
    Model -->|"Claims and uncertainty"| P3
    P3 -->|"Claim-evidence links"| D3
    P3 -->|"Evidence synthesis and candidate questions"| P4
    P4 -->|"Method/protocol/data plan"| Researcher
    Researcher -->|"Approved plan / constraints"| P4
    P4 -->|"Protocol and analysis specification"| D4
    D4 -->|"Supported data + approved config"| P5
    Researcher -->|"Permitted external-study results"| P5
    P5 -->|"Actual tables, statistics, charts"| D4
    P5 -->|"Observed results and limitations"| P6
    D3 -->|"Evidence and lineage"| P6
    D4 -->|"Protocol / actual analysis artifacts"| P6
    P6 -->|"Draft, citations, review state"| D5
    D5 -->|"Report and export"| Researcher

    classDef actor fill:#fff7ed,stroke:#c2410c,stroke-width:1.5px,color:#431407
    classDef process fill:#eff6ff,stroke:#2563eb,stroke-width:1.5px,color:#172554
    classDef store fill:#ecfdf5,stroke:#059669,stroke-width:1.5px,color:#022c22
    classDef external fill:#f8fafc,stroke:#94a3b8,stroke-width:1.5px,stroke-dasharray:5 4,color:#0f172a

    class Researcher actor
    class P1,P2,P3,P4,P5,P6 process
    class D1,D2,D3,D4,D5 store
    class Search,Web,Model external
```

P5 có hai nhánh: runner phân tích dữ liệu trong phạm vi hỗ trợ, hoặc nhà nghiên cứu tự làm lab/khảo sát/thực địa ngoài ATI rồi nạp kết quả. DFD không hàm ý ATI tự tiến hành nghiên cứu thực địa.

## 4. Inference Flow — Multi-Agent Workflow

Sơ đồ điều khiển thể hiện vai trò, bounded loops, nhánh loại nghiên cứu, ethics gate, tạm dừng/resume và điều kiện tạo Results. Các role là node trong workflow, không phải các dịch vụ độc lập.

```mermaid
flowchart TB
    Start(["Research question + optional uploads"])
    --> Supervisor["Supervisor<br/>classify task · draft plan · set budget"]

    Supervisor --> PlanGate{"Plan review required?"}
    PlanGate -->|"Yes"| WaitApproval["Save checkpoint<br/>WAITING_APPROVAL"]
    WaitApproval --> Decision{"User decision"}
    Decision -->|"Revise"| Supervisor
    Decision -->|"Cancel"| Cancelled(["CANCELLED"])
    Decision -->|"Approve"| EvidenceWork
    PlanGate -->|"No"| EvidenceWork

    EvidenceWork["Researcher + Curator<br/>search, fetch, deduplicate,<br/>ingest web and uploaded sources"]
    --> EvidenceAnalyst["Evidence Analyst<br/>claims, evidence, uncertainty,<br/>conflicts"]
    EvidenceAnalyst --> Synthesis["Synthesis<br/>candidate questions + search limits"]
    Synthesis --> Method["Methodology Designer<br/>article type, method, hypothesis,<br/>protocol"]

    Method --> Mode{"Study path"}
    Mode -->|"Literature review"| Draft
    Mode -->|"Supported computational"| DataGate
    Mode -->|"Lab / survey / field / participants"| Ethics["Ethics safeguard<br/>draft protocol only;<br/>show review notice"]

    Ethics --> Protocol(["Save/export protocol<br/>no recruitment or study start"])
    Protocol --> ProtocolChoice{"Continue toward results?"}
    ProtocolChoice -->|"No"| ProtocolOnly["Protocol-only output<br/>no empirical Results"]
    ProtocolOnly --> Validate
    ProtocolChoice -->|"Yes"| WaitData["Save checkpoint<br/>WAITING_USER_DATA<br/>worker job ends"]

    DataGate{"Data and approved<br/>analysis specification present?"}
    DataGate -->|"No"| WaitData
    DataGate -->|"Yes"| Supported{"Schema and routine<br/>supported?"}
    Supported -->|"No"| ManualResult
    Supported -->|"Yes"| Runner["Isolated runner<br/>approved routine · resource limits"]
    Runner --> Results["Data Analyst<br/>interpret actual output<br/>and limitations"]
    ManualResult["Researcher-provided analysis summary<br/>label as user supplied; retain provenance"] --> Results
    Results --> Draft

    WaitData --> UserWork["User performs external work if needed<br/>or uploads permitted input/result data"]
    UserWork --> Resume["Validate file/ownership;<br/>store artifact; enqueue resume"]
    Resume --> DataGate

    Draft["Writer<br/>use format for article type;<br/>Results need actual data"]
    --> Critic["Critic<br/>evidence, method fit,<br/>coverage and missing items"]
    Critic --> Verdict{"Review verdict"}
    Verdict -->|"REVISE"| MicroGuard{"Revision budget remains?"}
    MicroGuard -->|"Yes"| Revise["Writer revises requested sections"]
    MicroGuard -->|"No"| NeedsReview
    Revise --> Critic
    Verdict -->|"NEED_MORE_EVIDENCE"| Macro{"At most 3 loops,<br/>budget remains,<br/>new evidence likely?"}
    Macro -->|"Yes"| TargetSearch["Researcher searches missing evidence"]
    TargetSearch --> EvidenceWork
    Macro -->|"No"| Limited["Disclose unresolved questions<br/>and limitations"]
    Limited --> PartialValidator["Check citation lineage<br/>and retain disclosed gaps"]
    PartialValidator --> PartialIntegrity{"Citation lineage resolves?"}
    PartialIntegrity -->|"Yes"| Partial
    PartialIntegrity -->|"No"| NeedsReview

    Verdict -->|"PASS"| Validate["Deterministic validation<br/>citation lineage + result provenance"]
    Validate --> Integrity{"Citations and any required<br/>result artifacts resolve?"}
    Integrity -->|"Yes"| Finalize["Finalize output type:<br/>review · protocol · empirical article"]
    Integrity -->|"Repair attempt remains"| Draft
    Integrity -->|"Limit reached"| NeedsReview(["PARTIAL / NEEDS_REVIEW"])
    Finalize --> Complete(["COMPLETED"])
    Partial(["PARTIAL · limits disclosed"])

    Budget["Before each provider call:<br/>budget · timeout · retry limits"]
    Budget -.-> Supervisor
    Budget -.-> EvidenceWork
    Budget -.-> EvidenceAnalyst
    Budget -.-> Synthesis
    Budget -.-> Method
    Budget -.-> Draft
    Budget -.-> Critic
    Budget -.-> Revise
    Budget -.-> TargetSearch
    Budget -.-> Results

    classDef agent fill:#eff6ff,stroke:#2563eb,stroke-width:1.5px,color:#172554
    classDef decision fill:#fffbeb,stroke:#d97706,stroke-width:1.5px,color:#451a03
    classDef state fill:#f5f3ff,stroke:#7c3aed,stroke-width:1.5px,color:#2e1065
    classDef guard fill:#fff7ed,stroke:#ea580c,stroke-width:1.5px,color:#431407
    classDef terminal fill:#ecfdf5,stroke:#059669,stroke-width:1.5px,color:#022c22

    class Supervisor,EvidenceWork,EvidenceAnalyst,Synthesis,Method,Runner,Results,ManualResult,Draft,Critic,Revise,TargetSearch,Validate,PartialValidator,Finalize agent
    class PlanGate,Decision,Mode,ProtocolChoice,DataGate,Supported,Verdict,MicroGuard,Macro,Integrity,PartialIntegrity decision
    class WaitApproval,WaitData,Resume,Protocol,ProtocolOnly state
    class Ethics,Budget guard
    class Start,Cancelled,Complete,Partial,NeedsReview terminal
```

**Điều khiển bắt buộc:** macro research loop tối đa 3 vòng và dừng sớm nếu không tăng nguồn/evidence mới sau dedup; micro revision loop có giới hạn cấu hình; mọi provider call qua budget/timeout guard. WAITING_USER_DATA được lưu bền vững, worker kết thúc và chỉ job mới mới resume. Khi thiếu dữ liệu, không được tự điền Results. Autonomous mode chỉ áp dụng cho search/synthesis/revision có giới hạn; approval, ethics, dữ liệu thiếu hoặc hành động/chi phí vượt ngưỡng cần con người.

## 5. Asynchronous Sequence — Task, Pause and Resume

Thể hiện request ngắn, worker nền, event tiến độ và resume sau thời gian chờ không xác định; không giữ HTTP request hay Celery task chạy trong lúc người dùng làm nghiên cứu bên ngoài.

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Files as Object Storage
    participant Redis
    participant Worker as Celery Worker
    participant Graph as LangGraph
    participant Providers as Search / LLM
    participant Runner as Isolated Runner

    User->>UI: Submit question, study type, optional files
    UI->>API: POST research task
    API->>DB: Authorize and save task/plan
    API->>Files: Store authorized upload
    API->>Redis: Enqueue job
    API-->>UI: 202 Accepted + task_id
    UI->>API: Subscribe to task progress (SSE)
    API->>Redis: Subscribe to task event channel

    Redis-->>Worker: Deliver job
    Worker->>Graph: Start or resume checkpoint
    Graph->>Providers: Budget-guarded search/inference
    Providers-->>Graph: Sources and structured output
    Graph->>DB: Persist provenance, runs and state
    Worker-->>Redis: Publish progress/status
    Redis-->>API: Progress event
    API-->>UI: Current stage, state and warnings

    opt Plan approval requested
        Graph->>DB: Save checkpoint, WAITING_APPROVAL
        Worker-->>Redis: Publish waiting state and exit
        API-->>UI: Show plan for review
        User->>UI: Approve or revise
        UI->>API: Submit plan decision
        API->>DB: Persist decision
        API->>Redis: Enqueue plan-resume job
        Redis-->>Worker: Deliver resume job
        Worker->>Graph: Resume from checkpoint
    end

    opt Required user data is not yet available
        Graph->>DB: Save protocol/checkpoint, WAITING_USER_DATA
        Worker-->>Redis: Publish waiting state and exit
        API-->>UI: Show protocol, ethics notice and upload instructions
        Note over User: Obtain review and perform external study outside ATI
        User->>UI: Upload permitted results
        UI->>API: Submit result artifact
        API->>DB: Verify owner, file type and task state
        API->>Files: Store artifact and provenance
        API->>Redis: Enqueue resume after validated upload
        Redis-->>Worker: Deliver resume job
        Worker->>Graph: Resume from checkpoint
    end

    opt Supported computational analysis
        Graph->>Runner: Run supported analysis only
        Runner-->>Graph: Actual tables, statistics and chart artifacts
    end
    Graph->>Providers: Bounded writing and critique
    Providers-->>Graph: Type-specific draft
    Graph->>DB: Save report, citations and artifact lineage
    Worker-->>Redis: Publish terminal state
    Redis-->>API: COMPLETED / PARTIAL / NEEDS_REVIEW
    API-->>UI: Stream final status
    User->>UI: Read report or export
```

Upload, SSE, durable checkpoints, runner and resume are target requirements; baseline runtime chưa chứng minh các luồng này.

## 6. Core ERD — Target Traceability Model

ERD tập trung vào trục truy xuất: task/plan → source/evidence → data/analysis artifact → report/citation. Đây là mô hình mục tiêu, chưa phải inventory schema hiện tại.

```mermaid
erDiagram
    USER ||--o{ RESEARCH_TASK : owns
    RESEARCH_TASK ||--o{ RESEARCH_PLAN : versions
    RESEARCH_TASK ||--o{ RESEARCH_ITERATION : records
    RESEARCH_TASK ||--o{ RESEARCH_SOURCE : collects
    RESEARCH_SOURCE ||--o{ DOCUMENT_CHUNK : contains
    RESEARCH_TASK ||--o{ RESEARCH_CLAIM : extracts
    RESEARCH_SOURCE o|--o{ EVIDENCE : grounds
    DOCUMENT_CHUNK o|--o{ EVIDENCE : anchors
    RESEARCH_ARTIFACT o|--o{ EVIDENCE : grounds_computed_result
    RESEARCH_CLAIM ||--o{ CLAIM_EVIDENCE : supported_by
    EVIDENCE ||--o{ CLAIM_EVIDENCE : supports
    RESEARCH_TASK ||--o{ RESEARCH_ARTIFACT : stores
    RESEARCH_TASK ||--o{ ANALYSIS_RUN : executes
    RESEARCH_ARTIFACT ||--o{ ANALYSIS_RUN : input
    ANALYSIS_RUN ||--o{ RESEARCH_ARTIFACT : produces
    RESEARCH_TASK ||--o{ RESEARCH_REPORT : versions
    RESEARCH_REPORT ||--o{ CITATION : includes
    RESEARCH_CLAIM ||--o{ CITATION : cites
    DOCUMENT_CHUNK ||--o{ CITATION : resolves_to
    RESEARCH_TASK ||--o{ AGENT_RUN : observes

    USER {
        uuid id PK
        string email
    }
    RESEARCH_TASK {
        uuid id PK
        uuid user_id FK
        string study_type
        string execution_mode
        string report_type
        string status
        decimal budget_limit
    }
    RESEARCH_PLAN {
        uuid id PK
        uuid task_id FK
        int version
        string method
        string approval_status
    }
    RESEARCH_ITERATION {
        uuid id PK
        uuid task_id FK
        int iteration_no
        string verdict
        int new_source_count
    }
    RESEARCH_SOURCE {
        uuid id PK
        uuid task_id FK
        string source_type
        string url_or_storage_key
        string attribution
    }
    DOCUMENT_CHUNK {
        uuid id PK
        uuid source_id FK
        int chunk_index
        vector embedding
    }
    RESEARCH_CLAIM {
        uuid id PK
        uuid task_id FK
        text claim_text
        string confidence_label
    }
    EVIDENCE {
        uuid id PK
        uuid task_id FK
        uuid source_id FK
        uuid chunk_id FK
        uuid artifact_id FK
        text quote
    }
    CLAIM_EVIDENCE {
        uuid claim_id PK, FK
        uuid evidence_id PK, FK
    }
    RESEARCH_ARTIFACT {
        uuid id PK
        uuid task_id FK
        string artifact_type
        string storage_key
        string provenance
    }
    ANALYSIS_RUN {
        uuid id PK
        uuid task_id FK
        uuid input_artifact_id FK
        string routine_version
        string status
    }
    RESEARCH_REPORT {
        uuid id PK
        uuid task_id FK
        int version
        string article_type
        string completion_state
    }
    CITATION {
        uuid id PK
        uuid task_id FK
        uuid report_id FK
        uuid claim_id FK
        uuid source_id FK
        uuid chunk_id FK
    }
    AGENT_RUN {
        uuid id PK
        uuid task_id FK
        string node_name
        string status
        int duration_ms
        int token_count
        string correlation_id
    }
```

**Ràng buộc mục tiêu:** mọi source/chunk/evidence/claim/citation của một báo cáo phải cùng task; file nằm trong object storage nhưng owner, checksum, loại file, retention và lineage nằm trong metadata; AnalysisRun phải lưu routine/version, input/output artifact, config, thời gian và trạng thái.

Evidence phải có đúng một loại neo provenance: `source_id` + `chunk_id` cho bằng chứng từ tài liệu, hoặc `artifact_id` cho kết quả phân tích đã tạo. Artifact kết quả phải truy được về `AnalysisRun`, routine/version và input artifact. `CITATION` chỉ đại diện trích dẫn nguồn học thuật và vẫn resolve về source/chunk; không dùng citation thay cho provenance của artifact.

## 7. Phụ lục — Physical DFD

Bản ánh ánh xạ runtime; Redis/Celery/API chỉ có ở đây vì sơ đồ hỏi dữ liệu chạy giữa các thành phần triển khai thế nào.

Nghiên cứu lab/khảo sát/thực địa diễn ra ngoài ATI và không phải runtime component. Nhà nghiên cứu tự thực hiện theo protocol; kết quả được phép xử lý quay lại qua luồng upload của User/API và lưu artifact trong Object Storage.

```mermaid
flowchart LR
    User(["Researcher"])
    Search["Search provider"]
    Web(["Public websites"])
    LLM["LLM / embedding provider"]

    subgraph App["ATI runtime"]
        UI["Next.js"]
        API["FastAPI"]
        Broker[("Redis")]
        Worker["Celery + LangGraph"]
        DB[("PostgreSQL + pgvector")]
        Files[("Object storage")]
        Runner["Isolated analysis runner"]
        Observe["Logs / metrics / traces"]
    end

    User --> UI
    UI -->|"REST · upload · report"| API
    API -.->|"SSE events"| UI
    API -->|"task · checkpoint · artifact metadata"| DB
    API -->|"authorized file access"| Files
    API -->|"enqueue"| Broker
    Broker --> Worker
    Worker -->|"status · evidence · report"| DB
    Worker -->|"source and result artifacts"| Files
    Worker -->|"budget-guarded query"| Search
    Search --> Worker
    Worker --> Web
    Web --> Worker
    Worker --> LLM
    LLM --> Worker
    Worker -->|"approved analysis only"| Runner
    Runner -->|"reproducible output artifacts"| Worker
    Worker -->|"telemetry"| Observe
    API --> Observe
```

## 8. Phụ lục — Conceptual Class Diagram

Class view chỉ giữ entity và service cốt lõi; chi tiết ORM/API thuộc [data-model-and-api.md](../technical/data-model-and-api.md).

```mermaid
classDiagram
    direction LR
    class User
    class ResearchTask {
        study_type
        execution_mode
        report_type
        status
    }
    class ResearchPlan
    class ResearchSource
    class DocumentChunk
    class ResearchClaim
    class Evidence
    class ClaimEvidence
    class ResearchArtifact
    class AnalysisRun
    class ResearchReport
    class Citation
    class AgentRun
    class ResearchWorkflowService
    class IsolatedAnalysisService
    class CitationIntegrityValidator

    User "1" --> "0..*" ResearchTask : owns
    ResearchTask "1" *-- "0..*" ResearchPlan : versions
    ResearchTask "1" *-- "0..*" ResearchSource : collects
    ResearchSource "1" *-- "0..*" DocumentChunk : chunks
    ResearchTask "1" *-- "0..*" ResearchClaim : extracts
    ResearchClaim "1" --> "0..*" ClaimEvidence : links
    ClaimEvidence "0..*" --> "1" Evidence : cites
    ResearchTask "1" *-- "0..*" ResearchArtifact : stores
    ResearchArtifact "0..1" --> "0..*" Evidence : computed result provenance
    ResearchArtifact "1" --> "0..*" AnalysisRun : input
    AnalysisRun "1" --> "0..*" ResearchArtifact : output
    ResearchTask "1" *-- "0..*" ResearchReport : versions
    ResearchReport "1" *-- "0..*" Citation : includes
    ResearchTask "1" *-- "0..*" AgentRun : records
    ResearchWorkflowService ..> ResearchTask : orchestrates
    IsolatedAnalysisService ..> AnalysisRun : executes
    CitationIntegrityValidator ..> Citation : checks lineage
```

## 9. Hiện trạng và khoảng cách

Bằng chứng gần nhất được ghi trong baseline 27/09/2026 và cập nhật tài liệu 28/09/2026; chưa xác nhận lại runtime trong lần chỉnh tài liệu này.

| Năng lực | Bằng chứng hiện có | Còn thiếu tới target |
|---|---|---|
| Docker / PostgreSQL / Redis / Celery | Compose/services smoke-test; pgvector tồn tại; worker ping được | Recovery/load/security |
| FastAPI và task API | Health/OpenAPI, POST/GET task smoke-test | Auth, ownership và lifecycle routes |
| LangGraph | Compile, 5 routing smoke cases | E2E, reducer behavior, budget enforcement |
| Search/fetch/retrieval | Source code có | Provider thật, ingest/retrieval/provenance E2E |
| Report/citations | Model/node scaffold | Deterministic citation validator và semantic evaluation |
| Upload/object storage | Chưa xác minh | Upload ownership, validation, retention |
| Approval/data pause-resume | Chưa xác minh | Durable checkpoint và enqueue khi resume |
| Isolated runner | Chưa chọn/triển khai | ADR, threat model và resource/network isolation |
| UI progress/monitoring | Frontend starter, polling; SSE chưa mount | Stage/state events, structured logs, correlation |
| Image/PDF | Chưa xác minh E2E | Tùy chọn; không được làm chậm core workflow |

## 10. References

- [C4 Model — Diagrams](https://c4model.com/diagrams)
- [C4 Model — Notation](https://c4model.com/diagrams/notation)
- [IBM — Data Flow Diagrams](https://www.ibm.com/think/topics/data-flow-diagram)
- [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/About-UML)
- [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
- [Mermaid ER syntax](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)
- [Mermaid Sequence syntax](https://mermaid.js.org/syntax/sequenceDiagram.html)
- [LangGraph persistence and interrupts](https://docs.langchain.com/oss/python/langgraph/persistence)
- [PRISMA 2020 Statement](https://www.prisma-statement.org/prisma-2020)
