"""Pure formatting and citation-lineage helpers shared by writing roles."""

from typing import Any, Optional

from app.services.manuscript import normalize_claim_markers

def _report_sections(markdown: str, max_chars: int = 5000) -> list[tuple[str, str]]:
    from app.services.manuscript_structure import review_sections
    return review_sections(markdown, max_chars)


def _review_batches(sections: list[tuple[str, str]], max_chars: int = 9000) -> list[tuple[list[str], str]]:
    """Batch adjacent sections to reduce provider calls while reviewing every byte."""
    batches: list[tuple[list[str], str]] = []
    names: list[str] = []
    content = ""
    for name, body in sections:
        block = f"## {name}\n{body}"
        if content and len(content) + len(block) > max_chars:
            batches.append((names, content))
            names, content = [], ""
        names.append(name)
        content = f"{content}\n\n{block}" if content else block
    if content:
        batches.append((names, content))
    return batches


def _claim_lineage_findings(markdown: str, claims: list[dict[str, Any]]) -> list[str]:
    """Find report citation markers without a persisted claim/evidence/source/chunk chain."""
    import re

    valid_claim_ids = {
        str(item.get("claim_id"))
        for item in claims
        if item.get("claim_id") and item.get("evidence_id") and item.get("source_id") and item.get("chunk_id")
    }
    markdown = normalize_claim_markers(markdown)
    findings = [
        f"Citation marker {marker[:48]} has no verified claim → evidence → source → chunk lineage."
        for marker in re.findall(r"\[\[@claim:([^\]]+)\]\]", markdown)
        if marker not in valid_claim_ids
    ]
    without_markers = re.sub(r"\[\[@claim:[^\]]+\]\]", "", markdown)
    if "@claim:" in without_markers:
        findings.append("Malformed or incomplete claim citation marker; repair the marker without inventing evidence.")
    return findings

# ---------------------------------------------------------------------------
# 3. NODE FUNCTIONS (100% Async, Không Placeholder)
# ---------------------------------------------------------------------------

LANGUAGE_DIRECTIVES: dict[str, str] = {
    "en": "English. Write the entire scientific report, title, abstract, sections, headings, tables, analysis, and conclusion strictly in academic English.",
    "vi": "Tiếng Việt. Viết toàn bộ bài báo khoa học, tiêu đề, tóm tắt, các mục, bảng biểu, phân tích và kết luận bằng văn phong khoa học Tiếng Việt chuẩn mực.",
    "ja": "Japanese (日本語). 論文全体、要約、本文、見出し、考察、結論を学術的な日本語で正確に執筆してください。",
    "zh": "Chinese (中文). 请使用规范学术中文撰写完整学术论文、摘要、标题、正文各章节、分析及结论。",
    "fr": "French (Français). Rédiger l'intégralité de l'article scientifique, le titre, le résumé, les sections et la conclusion en français académique.",
    "de": "German (Deutsch). Verfassen Sie die gesamte wissenschaftliche Arbeit, Abstract, Abschnitte und Fazit auf akademischem Deutsch.",
    "es": "Spanish (Español). Redactar todo el artículo científico, título, resumen, secciones y conclusiones en español académico.",
    "ko": "Korean (한국어). 논문 전체, 초록, 본문, 각 장 및 결론을 학술적인 한국어로 정확하게 작성해 주십시오.",
}

def format_language_instruction(code: Optional[str]) -> str:
    if not code:
        return LANGUAGE_DIRECTIVES["en"]
    normalized = str(code).lower().strip()
    return LANGUAGE_DIRECTIVES.get(normalized, f"{code}. Write the entire paper strictly in {code}.")

def format_section_outline_prompt(section_outline: list[Any], contract: dict | None = None) -> str:
    if not section_outline and not contract:
        return ""
    lines = [
        "YÊU CẦU CẤU TRÚC TIÊU ĐỀ CON H3 (SUBSECTIONS):",
        "Mỗi phần thân bài chính (Synthesis, Review Methods, Methods, Setup, Results, Discussion) BẮT BUỘC phải tổ chức thành từ 2 đến 4 mục con H3 (### <Tiêu đề chuyên đề cụ thể>), không để mục trống, không chỉ liệt kê gạch đầu dòng. Sử dụng đề cương lập luận sau làm cấu trúc định hướng:",
    ]
    if section_outline:
        for sec in section_outline:
            sec_id = sec.get("section_id") if isinstance(sec, dict) else getattr(sec, "section_id", "")
            titles = sec.get("subsection_titles") if isinstance(sec, dict) else getattr(sec, "subsection_titles", [])
            purpose = sec.get("purpose") if isinstance(sec, dict) else getattr(sec, "purpose", "")
            titles_str = ", ".join(f"### {t}" for t in titles) if titles else "2–4 mục con H3"
            lines.append(f"- Phần '{sec_id}': Gồm các mục con {titles_str}. Mục tiêu: {purpose}")
    elif contract and contract.get("sections"):
        for s in contract.get("sections", []):
            if s.get("id") in ("synthesis", "review_methods", "methods", "setup", "results", "discussion"):
                lines.append(f"- Phần '{s.get('heading')}': Triển khai ít nhất 2 mục con '### <Chủ đề>' phân tích sâu.")
    return "\n".join(lines)
