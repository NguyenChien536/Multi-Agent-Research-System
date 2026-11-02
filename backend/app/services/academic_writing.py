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

# Original rhetorical blueprints informed by publisher instructions and papers.
# These are roles for subsections, not text/headings/results to copy verbatim.
_STRUCTURE = {
    "NARRATIVE_REVIEW": {
        "review_methods": "Separate the actual scope/source-discovery procedure from selection boundaries and how evidence was synthesized. Name executed indexes/queries and limits, not an invented screening protocol.",
        "synthesis": "Create question-specific themes or comparison dimensions. Within each theme compare supported findings, assumptions, disagreements and missing evidence; avoid one subsection per paper.",
    },
    "COMPUTATIONAL_STUDY": {
        "methods": "Separate the problem/variables/assumptions from the routine actually executed. Explain inputs, outputs, objective and methodological choices without describing an unexecuted proposed method as tested.",
        "setup": "Separate dataset/split/preprocessing from baselines/parameters/metrics. Include only recorded details, units and reproducibility settings; identify leakage safeguards and unrecorded information.",
        "results": "Group observations by research question or measured comparison: primary outcomes against the baseline, then documented robustness/repeatability/negative results when available. Never invent a second experiment to fill a heading.",
    },
    "EMPIRICAL_STUDY": {
        "methods": "Separate study design/data provenance/population from documented measures/collection/analysis. Attribute researcher-supplied information and explain consent/ethics status when documented.",
        "results": "Organize actual supplied observations by question/theme/outcome, with provenance and uncertainty. Separate sample/data completeness from substantive findings when both are documented. Do not convert a protocol into completed fieldwork.",
    },
}

_LENGTHS = {
    "SHORT": {"word_target": "600–900", "output_tokens": 8192},
    "MEDIUM": {"word_target": "1400–2000", "output_tokens": 12288},
    "LONG": {"word_target": "2400–3200", "output_tokens": 16384},
}


def writing_limits(contract, length):
    """Use frozen word/output profiles; absent historical profiles keep old limits."""
    profiles = ((contract or {}).get("writing_brief") or {}).get("length_profiles")
    if profiles:
        return profiles[length]["word_target"], profiles[length]["output_tokens"]
    return {"SHORT": ("400–600", 4096), "MEDIUM": ("800–1100", 8192),
            "LONG": ("1400–1800", 12288)}[length]


def structure_policy(article_type):
    if article_type not in _STRUCTURE:
        raise ValueError("Unsupported academic writing structure")
    return {"version": 1, "expand_after_characters": 350,
            "minimum_subsection_prose_characters": 50, "maximum_subsections": 6,
            "sections": {key: {"minimum_subsections": 2, "purpose": purpose}
                         for key, purpose in _STRUCTURE[article_type].items()}}


def writing_brief(article_type: str) -> dict:
    if article_type not in _METHODS:
        raise ValueError("Unsupported academic writing profile")
    return deepcopy({
        "version": 2, "article_type": article_type,
        "length_profiles": _LENGTHS,
        "length_rule": "Word ranges are targets for an evidence-sufficient manuscript, not a minimum to fill with speculation. Write less and identify missing evidence when necessary. Preserve the total task token/cost/time budget; a longer configured output cap does not authorize more unsupported claims or unbounded revisions.",
        "section_goals": {**_COMMON, **_METHODS[article_type]},
        "paragraph_rule": "Develop a question-relevant claim, its evidence with attribution, the reasoning that connects them, and its scope or uncertainty. Vary paragraph form naturally; do not repeat a four-sentence formula or decorative transitions.",
        "visual_rule": "Use figures to explain an argument or measured comparison, not decorate the paper. Introduce and interpret every numbered figure/table near first use, in numerical order. Captions state what, how, scope and provenance; accessible descriptions explain key structure/values without relying on color. Never infer error bars from one result. Put a table caption on its own line in the form 'Table N. <specific caption>' directly before its Markdown table; do not use a generic 'comparison' caption.",
        "reference_rule": "Cite only supplied verified claim markers where evidence is used. Check that the quoted evidence supports the specific inference and population/setting; a valid URL is not proof of support. Preserve disagreement. Never cite a paper just to make the bibliography look scholarly or copy an exemplar's bibliography.",
        "technical_claim_rule": "State theorem assumptions and the specific model/variant. Keep stability, strategy-proofness, welfare and demographic fairness distinct. A guarantee for transformed inputs does not imply a guarantee for the original inputs. A qualitative synthesis cannot prove that a proposed hybrid resolves a trade-off. Require a cited formal result or executed evaluation for such a conclusion; otherwise describe it as a hypothesis with validation still needed.",
        "method_specification_rule": "When proposing a technical method, define its inputs, outputs, constraints, objective directions and measurable variables; mark proposed formulas as unexecuted. Define each fairness measure explicitly rather than equating balanced satisfaction with demographic fairness. Distinguish alternative pipeline designs and their different assumptions. Missing definitions are limitations, never silently filled with alleged results.",
        "hierarchy_rule": "Plan a coherent H2/H3 hierarchy before composing prose. Use the section policy to develop 2–4 informative H3 subsections in substantial analytical/method sections. Titles should identify the actual theme, mechanism, comparison or finding; never copy an exemplar's topic or force the same subsection labels on every subject. A parent heading may introduce children without its own paragraph. Keep short Abstract/Keywords/Introduction/Conclusion coherent; do not split every introductory rhetorical move into a separate heading. Use H4 only where needed beneath H3, without skipping levels. A short section need not be fragmented for a heading count.",
        "argument_rule": "Each developed subsection must answer a question relevant to this manuscript, attribute the available evidence, explain comparison or mechanism, and close with an implication or unresolved issue. Connect subsections with a progression toward the RQs rather than repetitive summaries. More headings do not replace substantive analysis. Missing evidence must remain an explicit limitation and must not be expanded into invented detail.",
        "exemplar_rule": "Learn genre, hierarchy, paragraph function, figure/table placement and citation practice from exemplars. Rebuild the argument for the current question and evidence; never transplant exemplar sentences, participant counts, metrics, references or unexecuted study designs. This is a general academic profile, not a claim of exact compliance with a named journal or a user exemplar that was never supplied.",
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
