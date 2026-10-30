"""Small synthetic manuscripts for integration tests; not scientific quality examples."""
import re
import json
from app.services.manuscript import manuscript_contract


def supported_critic_response(messages):
    """Synthetic support judgments for orchestration tests, not semantic accuracy."""
    from app.agents.nodes import CriticVerdict
    text = messages[0].content
    match = re.search(r"^EVIDENCE_REVIEW_UNITS_JSON: (.*)$", text, re.M)
    units = json.loads(match[1]) if match else []
    return CriticVerdict(verdict="PASS", evidence_reviews=[{
        "statement_id": unit["statement_id"], "judgment": "SUPPORTED",
        "reason": "Controlled fixture judgment for workflow testing.",
        "supporting_claim_ids": unit.get("claim_ids", []), "assumptions_preserved": True,
    } for unit in units])


def complete_manuscript(content, research_type="REVIEW", language="vi", prompt=""):
    contract = manuscript_contract(research_type, language)
    # Keep assertions about fixture-specific findings and source markers intact.
    body = re.sub(r"(?m)^#{1,6}\s+", "", content)
    paragraph = "This controlled test paragraph describes the available evidence and its limitations. Interpretation remains conditional on the supplied observations."
    sections = ["# Evidence-grounded research manuscript"]
    for section in contract["sections"]:
        text = "research; evidence; evaluation" if section["id"] == "keywords" else paragraph
        if section["id"] == "introduction":
            text += " RQ1: What does this controlled evaluation support? The research gap is bounded to the reviewed evidence; contributions are limited to exploratory synthesis."
            # Keep the supplied fixture's validated claim markers in the context
            # that motivates the question, as well as in synthesis/results.
            text += " " + " ".join(re.findall(r"\[\[@claim:[^\]]+\]\]", body))
        if section["id"] in {"synthesis", "results", "related_work"}:
            text += "\n\n" + body
        figure_ids = list(dict.fromkeys(re.findall(r"\[\[figure:([a-z_-]+)\]\]", prompt)))
        for number, figure_id in enumerate(figure_ids, 1):
            if (figure_id == "workflow" and section["id"] in {"review_methods", "methods"}) or (figure_id == "evaluation" and section["id"] == "results"):
                text += f"\n\nFigure {number} explains the controlled workflow or measured outcome and its limits; this synthetic fixture makes no claim of general superiority.\n\n[[figure:{figure_id}]]"
        sections.append(f"## {section['heading']}\n\n{text}")
    return "\n\n".join(sections)
