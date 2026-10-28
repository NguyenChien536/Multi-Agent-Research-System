"""Measured-figure construction and conservative scientific reporting gates."""
import math
import re
from copy import deepcopy
from xml.sax.saxutils import escape


def scientific_context(state: dict) -> dict:
    analysis = state.get("analysis_run") or {}
    return {"research_type": state.get("research_type", "REVIEW"),
            "grounded_claim_count": len({c.get("claim_id") for c in state.get("claims", []) if c.get("evidence_id")}),
            "evaluation_scope": "single_seeded_split_exploratory" if analysis else "literature_or_user_supplied_observations",
            "analysis": {key: deepcopy(analysis[key]) for key in (
                "analysis_run_id", "status", "routine_name", "metrics", "manifest", "reproducibility_status"
            ) if key in analysis},
            "statistical_significance_tested": False,
            "independent_datasets_evaluated": 1 if analysis else 0}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Figure metrics must be finite measured numbers")
    return float(value)


def build_scientific_figures(context: dict, provenance: dict) -> list[dict]:
    figures = []
    if provenance.get("available_source_count", 0):
        labels = ["Sources", "Evidence", "Synthesis"]
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="660" height="160" viewBox="0 0 660 160" role="img">',
               '<rect width="660" height="160" fill="white"/>']
        for i, label in enumerate(labels):
            x = 20 + i * 220
            svg += [f'<rect x="{x}" y="35" width="180" height="65" rx="6" fill="#eff6ff" stroke="#334155"/>',
                    f'<text x="{x+90}" y="74" text-anchor="middle" font-family="serif" font-size="20">{escape(label)}</text>']
            if i < 2:
                svg.append(f'<path d="M{x+182} 67h32m-8 -6 8 6-8 6" fill="none" stroke="#334155" stroke-width="2"/>')
        svg.append('</svg>')
        figures.append({"id": "workflow", "number": 1, "kind": "conceptual",
                        "caption": "Conceptual evidence-processing workflow. Arrows describe processing stages, not measured performance.",
                        "alt": "Sources feed evidence extraction, followed by synthesis.", "svg": "".join(svg),
                        "latex": r"\begin{tikzpicture}[every node/.style={draw,rounded corners,align=center,font=\small}]\node (s) at (0,0) {Sources};\node (e) at (2.2,0) {Evidence};\node (w) at (4.5,0) {Synthesis};\draw[->] (s)--(e);\draw[->] (e)--(w);\end{tikzpicture}"})
    run = context.get("analysis") or {}
    metrics = run.get("metrics") or {}
    if run.get("status") == "COMPLETED" and metrics.get("baseline") and metrics.get("model"):
        baseline = _number(metrics["baseline"]["mae"])
        model = _number(metrics["model"]["mae"])
        if min(baseline, model) < 0:
            raise ValueError("MAE cannot be negative")
        scale = max(baseline, model, 1e-12)
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="660" height="300" viewBox="0 0 660 300" role="img">',
               '<rect width="660" height="300" fill="white"/>',
               '<text x="330" y="25" text-anchor="middle" font-family="serif" font-size="17">Held-out MAE (lower is better)</text>',
               '<path d="M70 45v200h540" fill="none" stroke="#111827"/>']
        for x, value, label, color in [(150, baseline, "Mean baseline", "#94a3b8"), (390, model, "Ridge", "#334155")]:
            h = 165 * (value / scale)
            svg += [f'<rect x="{x}" y="{245-h:.3f}" width="120" height="{h:.3f}" fill="{color}"/>',
                    f'<text x="{x+60}" y="{230-h:.3f}" text-anchor="middle" font-family="serif" font-size="16">{value:.5g}</text>',
                    f'<text x="{x+60}" y="270" text-anchor="middle" font-family="serif" font-size="16">{label}</text>']
        svg.append('</svg>')
        n_test = (run.get("manifest") or {}).get("test_rows", "not recorded")
        figures.append({"id": "evaluation", "number": len(figures) + 1, "kind": "measured",
                        "caption": f"Held-out MAE in target units on {n_test} test rows. One seeded split is exploratory; no confidence intervals or significance test were computed.",
                        "alt": f"Mean baseline MAE {baseline:.5g}; Ridge MAE {model:.5g}.",
                        "svg": "".join(svg), "data": {"baseline_mae": baseline, "ridge_mae": model},
                        "latex": r"\begin{tikzpicture}\begin{axis}[ybar,width=\linewidth,height=4.5cm,ymin=0,ymax=1.25,xtick={1,2},xticklabels={Baseline,Ridge},ytick={0,0.5,1},yticklabels={0," + f"{scale/2:.4g},{scale:.4g}" + r"},ylabel={MAE (target units)},bar width=20pt]\addplot coordinates {(1," + f"{baseline/scale:.8f}" + ")(2," + f"{model/scale:.8f}" + r")};\end{axis}\end{tikzpicture}"})
    return figures


def figure_instructions(figures: list[dict]) -> str:
    if not figures:
        return "No approved figures are available. Do not invent plots or figure assets."
    lines = ["APPROVED FIGURES: use each supplied figure once. Write an explanatory paragraph referring to Figure N (or Hình N), then place its marker on a separate line in Methods/Results as appropriate."]
    for figure in figures:
        lines.append(f"Figure {figure['number']} ({figure['kind']}): {figure['caption']} Marker: [[figure:{figure['id']}]]")
    return "\n".join(lines)


def materialize_figures(markdown: str, figures: list[dict]) -> str:
    for f in figures:
        markdown = markdown.replace(f"[[figure:{f['id']}]]", f"![Figure {f['number']}. {f['caption']}](figures/{f['id']}.svg)")
    return markdown


def validate_scientific_reporting(markdown: str, contract: dict | None, context: dict, figures: list[dict]) -> list[dict]:
    if not contract or contract.get("version", 1) < 2:
        return []
    findings = []
    def add(code, message):
        findings.append({"code": code, "message": message})
    prose = re.sub(r"(?m)^!\[.*\]\(figures/[^)]+\)\s*$|\[\[figure:[^\]]+\]\]", "", markdown)
    for f in figures:
        marker = f"[[figure:{f['id']}]]"
        asset = f"](figures/{f['id']}.svg)"
        if marker not in markdown and asset not in markdown:
            add("FIGURE_MISSING", f"Include supplied Figure {f['number']} and its caption; do not invent an alternative plot.")
        matching = [p for p in prose.split("\n\n") if re.search(rf"(?:Figure|Fig\.?|Hình)\s*{f['number']}\b", p, re.I)
                    and not re.match(rf"\s*\*{{0,2}}(?:Figure|Fig\.?|Hình)\s*{f['number']}\s*[:.]", p, re.I)]
        if not any(len(p.split()) >= 12 for p in matching):
            add("FIGURE_UNEXPLAINED", f"Explain Figure {f['number']} in a substantive paragraph, including what it shows and its limits.")
    allowed = {f["id"] for f in figures}
    for name in re.findall(r"\[\[figure:([^\]]+)\]\]|\]\(figures/([^)]+)\.svg\)", markdown):
        if (name[0] or name[1]) not in allowed:
            add("UNKNOWN_FIGURE", "Use only figures produced from approved data or the labeled conceptual workflow.")
    run = context.get("analysis") or {}
    if contract.get("article_type") == "COMPUTATIONAL_STUDY":
        if run.get("status") != "COMPLETED" or not (run.get("metrics") or {}).get("baseline") or not (run.get("metrics") or {}).get("model"):
            add("BASELINE_MISSING", "Report real executed baseline/model results before making a computational comparison.")
    for section in contract.get("sections", []):
        if section["id"] not in {"related_work", "introduction", "results"}:
            continue
        match = re.search(rf"(?ms)^##\s+{re.escape(section['heading'])}\s*\n(.*?)(?=^##\s|\Z)", markdown)
        body = match[1] if match else ""
        if section["id"] in {"related_work", "introduction"} and context.get("grounded_claim_count", 0):
            if not re.search(r"\[\[@claim:|\[\d+\]|\([^\n)]+,\s*(?:\d{4}|n\.d\.)\)", body):
                add("UNCITED_RESEARCH_CONTEXT", f"Cite the source-backed comparisons and bounded gap in {section['heading']}.")
        if section["id"] == "results" and run.get("status") == "COMPLETED":
            for label, key in (("Ridge", "model"), ("(?:Mean baseline|baseline)", "baseline")):
                expected = ((run.get("metrics") or {}).get(key) or {}).get("mae")
                if expected is None:
                    continue
                for value in re.findall(rf"\b{label}\b[^\n.]{{0,50}}\bMAE\b\s*(?:=|of|is|là|:)\s*(-?\d+(?:\.\d+)?)", body, re.I):
                    if not math.isclose(float(value), float(expected), rel_tol=1e-3, abs_tol=1e-3):
                        add("METRIC_MISMATCH", "A reported MAE differs from the executed result; copy measured values and label their scope.")
    if re.search(r"(?m)^\s*\|.+\|\s*$", markdown) and not re.search(r"(?:Table|Bảng)\s*\d+", prose, re.I):
        add("TABLE_UNEXPLAINED", "Number and caption each table and explain it in the surrounding text.")
    for sentence in re.split(r"[.!?\n;]|\bbut\b|\bhowever\b|\bnhưng\b|\btuy nhiên\b", prose, flags=re.I):
        lowered = sentence.lower()
        if re.search(r"\b(not|no|without|không|chưa)\b", lowered):
            continue
        if re.search(r"significantly (?:better|outperform)|statistically significant|vượt trội có ý nghĩa|có ý nghĩa thống kê", lowered) and not context.get("statistical_significance_tested"):
            add("UNSUPPORTED_SIGNIFICANCE", "No statistical significance test was executed; report descriptive differences and exploratory limits.")
        if re.search(r"\b(?:best (?:model|method|algorithm|performance)|perfect (?:accuracy|performance|results))\b", lowered):
            add("UNSUPPORTED_SUPERLATIVE", "Replace absolute superiority claims with a specific supported comparison and its evaluation scope.")
        if context.get("independent_datasets_evaluated", 0) <= 1 and re.search(r"across all datasets|in all cases|universally superior|mọi bộ dữ liệu|vượt trội trên tất cả", lowered):
            add("UNSUPPORTED_GENERALIZATION", "One limited evaluation cannot justify a universal performance claim.")
    return findings
