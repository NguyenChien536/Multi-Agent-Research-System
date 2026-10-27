"""Small synthetic manuscripts for integration tests; not scientific quality examples."""
import re
from app.services.manuscript import manuscript_contract


def complete_manuscript(content, research_type="REVIEW", language="vi"):
    contract = manuscript_contract(research_type, language)
    # Keep assertions about fixture-specific findings and source markers intact.
    body = re.sub(r"(?m)^#{1,6}\s+", "", content)
    paragraph = "This controlled test paragraph describes the available evidence and its limitations. Interpretation remains conditional on the supplied observations."
    sections = ["# Evidence-grounded research manuscript"]
    for section in contract["sections"]:
        text = "research; evidence; evaluation" if section["id"] == "keywords" else paragraph
        if section["id"] in {"synthesis", "results"}:
            text += "\n\n" + body
        sections.append(f"## {section['heading']}\n\n{text}")
    return "\n\n".join(sections)
