from typing import TypedDict, List, Dict, Set, Any, Optional


class ResearchBudget(TypedDict):
    """Giới hạn tài nguyên cho mỗi Research Task — chống đội chi phí và lặp vô hạn."""
    max_iterations: int               # Mặc định: 3
    max_sources: int                  # Mặc định: 20
    max_search_queries: int           # Mặc định: 30
    max_llm_calls: int                # Mặc định: 50
    max_input_tokens: int             # Mặc định: 100000
    max_output_tokens: int            # Mặc định: 50000
    max_cost_usd: float               # Mặc định: 2.0
    timeout_seconds: int              # Mặc định: 300 (5 phút)
    
    # Tracking hiện tại
    current_llm_calls: int
    current_input_tokens: int
    current_output_tokens: int
    current_cost_usd: float
    elapsed_seconds: float


class ResearchState(TypedDict):
    """Trạng thái dùng chung (Shared Graph State) trong LangGraph."""
    # === Cấu hình Task ===
    task_id: str
    user_id: str
    research_question: str
    research_depth: str               # 'SHALLOW' | 'STANDARD' | 'DEEP'
    language: str
    budget: ResearchBudget            # Giới hạn tài nguyên toàn bộ task
    max_micro_revisions: int          # Giới hạn Micro-loop Writer ⟷ Critic (mặc định: 2)
    current_iteration: int
    current_micro_revision: int       # Đếm số lần Writer chỉnh sửa trong vòng hiện tại
    attempt_number: int               # Số lần retry (cho Worker crash recovery)
    
    # === Kế hoạch & Truy vấn ===
    plan: Dict[str, Any]              # Đề cương & danh sách câu hỏi con
    current_queries: List[str]        # Danh sách queries hiện tại (ban đầu hoặc Delta Queries)
    visited_urls: Set[str]            # URLs đã crawl — tránh lặp ở vòng sau (Seen URL Cache)
    
    # === Dữ liệu thu thập ===
    collected_sources: List[Dict[str, Any]]    # Metadata các nguồn đã qua Curator
    source_id_mapping: Dict[str, Dict[str, Any]] # Ánh xạ source_tag (src_01) -> URL/Title
    indexed_chunks_count: int         # Số chunk đã index vào VectorDB
    
    # === Bằng chứng & Luận điểm (Evidence/Claim Chain) ===
    evidences: List[Dict[str, Any]]   # Danh sách Evidence đã trích xuất
    claims: List[Dict[str, Any]]      # Danh sách Claims đã rút ra từ Evidence
    
    # === Phân tích ===
    analysis_results: Dict[str, Any]  # Luận điểm, mâu thuẫn, phát hiện chính (kèm chunk_id)
    
    # === Viết & Phản biện ===
    draft_report_markdown: str        # Bản nháp từ Writer (có tag @src_xx)
    critic_verdict: str               # 'PASS' | 'REVISE' | 'NEED_MORE_DATA'
    critic_feedback: List[str]        # Feedback chi tiết: câu nào sai, thiếu gì
    critic_missing_areas: List[str]   # Danh sách knowledge gaps -> sinh Delta Queries
    citation_validation: Dict[str, Any] # Kết quả Citation Validator: valid/invalid counts
    
    # === Kết quả cuối cùng ===
    final_report_markdown: str        # Báo cáo sau Post-Processor (citation đã đánh số [1], [2])
    citations: List[Dict[str, Any]]   # Danh sách trích dẫn hoàn chỉnh
    errors: List[str]                 # Lỗi phát sinh trong quá trình
