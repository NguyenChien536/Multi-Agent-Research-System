import operator
from typing import Annotated, TypedDict, List, Dict, Set, Any, Optional


def merge_sets(left: Optional[Set[str]], right: Optional[Set[str]]) -> Set[str]:
    """Reducer gộp tập hợp URL đã crawl (Seen URL Cache) qua các vòng lặp."""
    return (left or set()).union(right or set())


def merge_dicts(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reducer cập nhật bảng mapping metadata nguồn mới vào bảng cũ."""
    res = dict(left or {})
    res.update(right or {})
    return res


class ResearchBudget(TypedDict):
    """Giới hạn tài nguyên cho mỗi Research Task — chống đội chi phí và lặp vô hạn."""
    max_iterations: int               # Mặc định: 3
    max_sources: int                  # Mặc định: 20
    max_search_queries: int           # Mặc định: 30
    max_llm_calls: int                # Mặc định: 40; provider attempts include fallbacks/retries
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


class ResearchState(TypedDict, total=False):
    """Trạng thái dùng chung (Shared Graph State) trong LangGraph với Annotated Reducers."""
    # === Cấu hình Task ===
    task_id: str
    workflow_run_id: str
    user_id: str
    research_question: str
    research_depth: str               # 'SHALLOW' | 'STANDARD' | 'DEEP'
    research_type: str                # 'REVIEW' | 'EMPIRICAL_COMPUTATIONAL' | 'EMPIRICAL_HUMAN'
    language: str
    budget: ResearchBudget            # Giới hạn tài nguyên toàn bộ task
    require_plan_approval: bool       # Bật chế độ Human-in-the-Loop (mặc định: False)
    plan_approved: bool               # Người dùng đã duyệt kế hoạch hay chưa
    plan_feedback: Optional[str]      # Góp ý hoặc yêu cầu điều chỉnh của người dùng
    protocol: Optional[Dict[str, Any]] # Phương pháp và đề cương nghiên cứu (Methodologist)
    protocol_artifact_id: Optional[str] # UUID của artifact protocol
    user_data_submission: Optional[Dict[str, Any]] # Dữ liệu/kết quả thực địa do người dùng cung cấp
    dataset_csv: Optional[str]        # Nội dung dataset CSV cho thực nghiệm tính toán
    analysis_run: Optional[Dict[str, Any]] # Kết quả thực thi routine thực nghiệm tính toán
    experiment_journal: Optional[List[Dict[str, Any]]] # Các entry nhật ký thí nghiệm (append-only)
    max_micro_revisions: int          # Giới hạn Micro-loop Writer ⟷ Critic (mặc định: 2)
    current_iteration: int
    current_micro_revision: int       # Đếm số lần Writer chỉnh sửa trong vòng hiện tại
    attempt_number: int               # Số lần retry (cho Worker crash recovery)
    max_iterations: int               # Giới hạn macro-loop, lấy từ budget nếu không truyền riêng
    current_agent: str                # Node gần nhất cập nhật trạng thái
    status: str                       # Trạng thái workflow hiện tại, gồm COMPLETED hoặc NEEDS_REVIEW
    
    # === Kế hoạch & Truy vấn (Có Reducer) ===
    plan: Dict[str, Any]              # Đề cương & danh sách câu hỏi con
    plan_version: int
    current_queries: Annotated[List[str], operator.add]   # Tích lũy queries qua các vòng
    delta_queries: List[str]          # Truy vấn của vòng hiện tại; được thay thế khi lập kế hoạch bổ sung
    visited_urls: Annotated[Set[str], merge_sets]         # URLs đã crawl — tránh lặp ở vòng sau (Seen URL Cache)
    
    # === Dữ liệu thu thập (Có Reducer) ===
    collected_sources: Annotated[List[Dict[str, Any]], operator.add] # Metadata các nguồn đã qua Curator
    source_id_mapping: Annotated[Dict[str, Dict[str, Any]], merge_dicts] # Ánh xạ source_tag (src_01) -> URL/Title
    indexed_chunks_count: int         # Số chunk đã index vào VectorDB
    
    # === Bằng chứng & Luận điểm (Evidence/Claim Chain - Có Reducer) ===
    evidences: Annotated[List[Dict[str, Any]], operator.add]   # Danh sách Evidence đã trích xuất
    claims: Annotated[List[Dict[str, Any]], operator.add]      # Danh sách Claims đã rút ra từ Evidence
    
    # === Phân tích ===
    analysis_results: Dict[str, Any]  # Luận điểm, mâu thuẫn, phát hiện chính (kèm chunk_id)
    
    # === Viết & Phản biện (Ủy quyền cho Subgraph) ===
    draft_report_markdown: str        # Bản nháp từ Writer (có marker claim để tạo citation đã kiểm chứng)
    critic_verdict: str               # 'PASS' | 'REVISE' | 'NEED_MORE_DATA'
    critic_feedback: List[str]        # Feedback chi tiết: câu nào sai, thiếu gì
    critic_missing_areas: List[str]   # Danh sách knowledge gaps -> sinh Delta Queries
    critic_review_metadata: Dict[str, Any] # Section coverage and bounded review findings
    citation_validation: Dict[str, Any] # Kết quả Citation Validator: valid/invalid counts
    
    # === Kết quả cuối cùng ===
    final_report_markdown: str        # Báo cáo sau Post-Processor (citation khớp claim/evidence đã lưu)
    citations: List[Dict[str, Any]]   # Danh sách trích dẫn hoàn chỉnh
    errors: Annotated[List[str], operator.add] # Lỗi phát sinh trong quá trình
