"""Scope-aware protocol guidance and conservative transport-format repair."""
import re


def protocol_constraints(research_type: str) -> str:
    common = """A protocol is proposed work, not an account of completed research.
Use questions appropriate to the requested design. For descriptive/exploratory work,
hypotheses may be an empty list; do not force significance tests or causal claims.
Do not invent a sample size, validated instrument, power calculation, ethics approval,
variables absent from the question, or claims that data already exists. Any suggested
sample size/instrument must be explicitly provisional with rationale and validation needs.
Honor synthetic/test-only scope; never describe synthetic rows as recruited participants.
Research gaps require actual literature support. A protocol alone establishes no gap.
Write actual newline characters in Markdown, not literal backslash-n sequences.
"""
    if research_type == 'EMPIRICAL_COMPUTATIONAL':
        return common + """
EXECUTABLE SCOPE: only tabular_regression_v1 on a user-uploaded numeric CSV.
The last numeric column is the target, remaining columns are features. At least 10
complete rows are required. The routine uses a seeded random 80/20 split, seed 42,
training-only standardization, Ridge alpha=1 and a mean-prediction baseline.
Metrics: MAE, RMSE, R-squared. Repeatability reruns the SAME frozen data/configuration.
It does not execute cross-validation, multi-seed robustness, hyperparameter tuning,
significance tests, arbitrary model code or a chronological forecast evaluation.
Do not put these unsupported operations into the executable RQs or analysis plan.
They may only appear as clearly labeled future work. A synthetic random split is
not evidence of performance on future real-world observations.
"""
    return common + """
HUMAN-LED SCOPE: the researcher performs collection outside the system and uploads
a file plus sample_size, method_notes, results_summary and data_provenance.
The system does not recruit people, grant ethics approval or automatically execute
Pearson correlations, regression or inferential statistics on the uploaded file.
Any such analysis is a suggested researcher action, not a promised automated step.
For a descriptive question, use descriptive RQs and only measures actually requested.
Keep intended sample size separate from the later uploaded observation count.
"""


def normalize_protocol_markdown(markdown: str) -> str:
    # Only repair an unmistakably double-escaped whole Markdown document.
    # Already multiline content, formulas, paths and code remain intact.
    if '\n' in markdown or not re.search(r'\\n\\n#{1,6} ', markdown):
        return markdown
    protected = r'(```[\s\S]*?```|`[^`]+`|\$\$[\s\S]*?\$\$|\$[^$]+\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])'
    return ''.join(part if i % 2 else part.replace('\\n', '\n')
                   for i, part in enumerate(re.split(protected, markdown)))
