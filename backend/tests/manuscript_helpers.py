"""Small synthetic manuscripts for integration tests; not scientific quality examples."""
import re
from app.services.manuscript import manuscript_contract


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
