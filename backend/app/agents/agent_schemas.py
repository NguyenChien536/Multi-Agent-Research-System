"""Validated structured outputs exchanged between research agents."""
from typing import Annotated, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.services.evidence_review import EvidenceReview


class ArgumentSection(BaseModel):
    section_id: str = Field(max_length=40, description="Semantic parent: review_methods, synthesis, methods, setup, results or discussion, consistent with study type")
    subsection_titles: List[str] = Field(min_length=2, max_length=4, description="Concise, topic-specific analytical H3 headings in output language; no alleged findings before evidence")
    purpose: str = Field(max_length=500, description="Question/comparison this parent section must develop; not fabricated evidence or results")


class EvidenceNeed(BaseModel):
    need_id: str = Field(min_length=1, max_length=40, description="Stable short ID unique within this plan")
    question: str = Field(min_length=1, max_length=350, description="One external-literature question needing source evidence; actual results on the user's dataset belong to executed analysis, not web discovery")
    search_query: str = Field(min_length=1, max_length=180, description="Short discovery query aligned with this evidence need; no invented author, title or DOI")
    section_id: str = Field(min_length=1, max_length=40, description="Intended semantic manuscript section, not a claimed finding")
    role: Literal["FOUNDATION", "CORE_CONCEPT", "COMPARISON", "LIMITATION", "COUNTEREVIDENCE"] = "CORE_CONCEPT"


class MetadataAssessment(BaseModel):
    candidate_id: str = Field(max_length=8)
    relevance: Literal["DIRECT", "CONTEXT", "OUT_OF_SCOPE", "UNCERTAIN"]
    study_role: Literal["PRIMARY", "REVIEW", "GUIDE", "UNCERTAIN"]
    reason: str = Field(max_length=300)
    need_ids: List[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default_factory=list, max_length=5)


class SourceTriage(BaseModel):
    assessments: List[MetadataAssessment] = Field(default_factory=list, max_length=24)


class SupervisorPlan(BaseModel):
    research_angle: str = Field(description="Góc nhìn và phương pháp tiếp cận đề tài")
    search_queries: List[str] = Field(max_length=5, description="Danh sách các truy vấn tìm kiếm (tối đa 5)")
    required_sections: List[str] = Field(description="Các mục bắt buộc phải có trong báo cáo")
    section_outline: List[ArgumentSection] = Field(default_factory=list, max_length=6, description="Provisional topic-specific hierarchy; Writer must adapt it to retrieved evidence")
    evidence_needs: List[EvidenceNeed] = Field(default_factory=list, max_length=5, description="Distinct evidence needs spanning principal concepts, foundational work, comparisons and limitations; align with the same search query budget")

class CriticVerdict(BaseModel):
    verdict: str = Field(description="PASS, REVISE, NEED_MORE_DATA, or NEEDS_REVIEW")
    feedback: List[str] = Field(default_factory=list, description="At most five concise, actionable findings grounded in supplied evidence; no rewritten manuscript")
    missing_areas: List[str] = Field(default_factory=list, description="At most five short, concrete evidence gaps that another search may address")
    evidence_reviews: List[EvidenceReview] = Field(default_factory=list, max_length=32)

class ExtractedClaim(BaseModel):
    claim: str = Field(description="Luận điểm chính được rút ra")
    evidence_quote: str = Field(description="Trích dẫn nguyên văn làm bằng chứng")
    chunk_id: Optional[str] = Field(default=None, max_length=36, description="Exact supplied Chunk ID containing this verbatim quote")
    evidence_need_id: Optional[str] = Field(default=None, max_length=40)
    assumptions: List[str] = Field(default_factory=list, max_length=8, description="Verbatim condition/limitation snippets from the same supplied chunk; do not infer missing assumptions")

class AnalystExtraction(BaseModel):
    claims: List[ExtractedClaim] = Field(max_length=6, description="At most six distinct, relevant claim/quote pairs; return none if supplied passages do not support the question")


class StudyPlanFields(BaseModel):
    research_questions: List[str] = Field(description="Các câu hỏi nghiên cứu cụ thể cần giải quyết")
    hypotheses: List[str] = Field(description="Testable hypotheses when appropriate; return an empty list for descriptive or exploratory research")
    study_design: str = Field(description="Thiết kế nghiên cứu, đối tượng khảo sát/thực nghiệm, cỡ mẫu dự kiến")
    data_collection_procedure: str = Field(description="Quy trình thu thập dữ liệu chi tiết")
    analysis_plan: str = Field(description="Kế hoạch phân tích thống kê và kiểm định giả thuyết")
    ethical_considerations: str = Field(description="Các lưu ý về đạo đức nghiên cứu và bảo mật dữ liệu")


class ProtocolVariableGroup(BaseModel):
    role: str = Field(min_length=1, max_length=80, description='Variable-group role, e.g. independent, dependent, control, or another relevant role')
    names: List[str] = Field(description='Variables explicitly relevant to this research question')


class MethodologistPlan(StudyPlanFields):
    variables: List[ProtocolVariableGroup] = Field(description='Named variable groups; use a list of role/names objects, not a free-form dictionary')


class MethodologistProtocol(StudyPlanFields):
    """Persisted protocol shape; Markdown is rendered from the validated plan."""
    protocol_markdown: str = Field(description="Bản đề cương nghiên cứu hoàn chỉnh định dạng Markdown")
    variables: Dict[str, List[str]] = Field(description='Persisted role-to-variable mapping')
