"""Original writing guidance distilled from publisher guidance, not exemplar prose.

The brief is frozen in the manuscript contract. It supplies rhetorical goals, not
scientific facts, citations, sample results or a promise of publication readiness.
"""
import json
from copy import deepcopy


_COMMON = {
    "abstract": "Write a self-contained compact paragraph: purpose/question, actual method, principal supported finding, and bounded implication. Write it after the body conceptually; do not invent a result, cite sources, or advertise novelty. A review reports a synthesis, not a new experiment.",
    "introduction": "Move from relevant context to a concrete problem, cited limitations of prior work, explicit RQs, the actual approach and supported contributions. Explain why the gap matters; no claim that a small search proves no prior research exists.",
    "related_work": "Compare studies along relevant common dimensions (assumptions, method, evidence, scope and limitations). Attribute each borrowed finding locally. Explain disagreements and non-comparable settings instead of describing one paper per paragraph or ranking incompatible metrics.",
    "discussion": "Answer the RQs using the reported evidence. Separate observation, interpretation, alternative explanations and implications. Compare with prior work with attribution; examine counterevidence and negative outcomes. Do not just repeat Results or turn association into causation.",
    "limitations": "Identify concrete limits of source selection, measurement, sample, design and transfer to other settings; explain which conclusions each limit weakens and what evidence would be needed next.",
    "conclusion": "Return to the question and give the bounded answer and actual contribution. No new evidence, numerical claims or recommendations stronger than the body; future work is explicitly unexecuted.",
}
_METHODS = {
    "NARRATIVE_REVIEW": {
        "review_methods": "Describe only recorded searches, supplied PDFs or reused sources, selection scope and synthesis approach. State non-systematic coverage and source-quality limits. Do not invent study screening counts or a PRISMA flow.",
        "synthesis": "Organize by questions/themes, not a catalogue of papers. Develop agreements, disagreements, assumptions and missing evidence with nearby claim markers. Distinguish findings in cited studies from your synthesis and tentative research directions.",
    },
    "COMPUTATIONAL_STUDY": {
        "methods": "Define the task, inputs, target, assumptions and executed routine with enough detail to reproduce it. Motivate choices with literature; distinguish proposed algorithms from the routine actually run.",
        "setup": "Report only available dataset provenance, valid/train/test counts, feature/target selection, split/seed, preprocessing, hyperparameters, baseline and metric definitions. Explain leakage safeguards when recorded; explicitly mark unrecorded details instead of assuming them.",
        "results": "Report baseline and model on the same evaluation, including negative or inconclusive comparisons and failures. State metrics and target units when known. Keep measured observations here and broader interpretation in Discussion; one split is exploratory, not statistical significance.",
    },
    "EMPIRICAL_STUDY": {
        "methods": "Report the supplied protocol, population/sample, recruitment/collection, variables/instruments, analysis and consent/ethics status only when documented. Missing approvals remain missing. The uploaded file and researcher summary are user-supplied, not independently verified fieldwork.",
        "results": "Attribute outcomes to the supplied data/summary; distinguish direct observations from any analysis actually executed. Report contradictions, missingness and adverse/negative findings. Do not turn a protocol into completed recruitment or invent inferential statistics.",
    },
}


def writing_brief(article_type: str) -> dict:
    if article_type not in _METHODS:
        raise ValueError("Unsupported academic writing profile")
    return deepcopy({
        "version": 1, "article_type": article_type,
        "section_goals": {**_COMMON, **_METHODS[article_type]},
        "paragraph_rule": "Develop a question-relevant claim, its evidence with attribution, the reasoning that connects them, and its scope or uncertainty. Vary paragraph form naturally; do not repeat a four-sentence formula or decorative transitions.",
        "visual_rule": "Use figures to explain an argument or measured comparison, not decorate the paper. Introduce and interpret every numbered figure/table near first use, in numerical order. Captions state what, how, scope and provenance; accessible descriptions explain key structure/values without relying on color. Never infer error bars from one result. Put a table caption on its own line in the form 'Table N. <specific caption>' directly before its Markdown table; do not use a generic 'comparison' caption.",
        "reference_rule": "Cite only supplied verified claim markers where evidence is used. Check that the quoted evidence supports the specific inference and population/setting; a valid URL is not proof of support. Preserve disagreement. Never cite a paper just to make the bibliography look scholarly or copy an exemplar's bibliography.",
        "review_criteria": [
            "question_to_conclusion_alignment", "evidence_to_inference_support",
            "comparison_and_counterevidence", "method_and_execution_honesty",
            "visual_interpretation_and_provenance", "local_attribution_and_reference_identity",
        ],
    })


def writing_guidance(contract: dict | None, *, reviewer: bool = False) -> str:
    brief = (contract or {}).get("writing_brief")
    if not brief:
        return ""  # Historical contracts retain their original editorial policy.
    purpose = ("Review only the supplied sections against the relevant goals. Do not mark unseen sections as reviewed. For each material issue, name the section, the problematic claim or figure and a feasible correction. Do not equate a matching citation marker with semantic support."
               if reviewer else "Use these section goals to plan the argument before drafting; return the article only. Do not expose this brief as a checklist or repeat its wording as manuscript content.")
    return "ACADEMIC WRITING BRIEF (guidance, not research evidence):\n" + json.dumps(brief, ensure_ascii=False) + "\n" + purpose
