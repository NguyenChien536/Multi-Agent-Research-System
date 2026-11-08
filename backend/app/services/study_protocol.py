"""Scope-aware protocol guidance and conservative transport-format repair."""
import re


def render_protocol(plan: dict, language: str = 'en') -> str:
    """Present validated method fields once, without a second generated narrative.

    The protocol is proposed work. Historical saved Markdown is not regenerated.
    """
    labels = {
        'en': ('Proposed Study Protocol', 'Research questions', 'Hypotheses', 'Variables', 'Study design', 'Data collection procedure', 'Analysis plan', 'Ethics and data protection', 'Not specified; researcher review required.'),
        'vi': ('Đề cương nghiên cứu đề xuất', 'Câu hỏi nghiên cứu', 'Giả thuyết', 'Biến nghiên cứu', 'Thiết kế nghiên cứu', 'Quy trình thu thập dữ liệu', 'Kế hoạch phân tích', 'Đạo đức và bảo vệ dữ liệu', 'Chưa xác định; cần người nghiên cứu rà soát.'),
        'ja': ('研究計画案', '研究課題', '仮説', '変数', '研究デザイン', 'データ収集手順', '分析計画', '倫理とデータ保護', '未指定。研究者による確認が必要です。'),
        'zh': ('拟议研究方案', '研究问题', '假设', '变量', '研究设计', '数据收集流程', '分析计划', '伦理与数据保护', '尚未指定，需研究者审核。'),
        'ko': ('제안된 연구 계획', '연구 질문', '가설', '변수', '연구 설계', '데이터 수집 절차', '분석 계획', '윤리 및 데이터 보호', '지정되지 않음. 연구자 검토가 필요합니다.'),
        'fr': ('Protocole de recherche proposé', 'Questions de recherche', 'Hypothèses', 'Variables', 'Plan de recherche', 'Collecte des données', "Plan d’analyse", 'Éthique et protection des données', 'Non précisé ; vérification par le chercheur requise.'),
        'de': ('Vorgeschlagenes Studienprotokoll', 'Forschungsfragen', 'Hypothesen', 'Variablen', 'Studiendesign', 'Datenerhebung', 'Analyseplan', 'Ethik und Datenschutz', 'Nicht angegeben; Prüfung durch Forschende erforderlich.'),
        'es': ('Protocolo de estudio propuesto', 'Preguntas de investigación', 'Hipótesis', 'Variables', 'Diseño del estudio', 'Recopilación de datos', 'Plan de análisis', 'Ética y protección de datos', 'No especificado; requiere revisión del investigador.'),
    }.get(language or 'en')
    if labels is None:
        return render_protocol(plan, 'en')
    keys = ('research_questions', 'hypotheses', 'variables', 'study_design',
            'data_collection_procedure', 'analysis_plan', 'ethical_considerations')
    parts = ['# ' + labels[0]]
    for key, heading in zip(keys, labels[1:8]):
        value = plan.get(key)
        if isinstance(value, dict):
            body = '\n'.join('- ' + str(name) + ': ' + '; '.join(str(v) for v in items)
                             for name, items in value.items())
        elif isinstance(value, list):
            body = '\n'.join('- ' + str(item) for item in value)
        else:
            body = str(value or '').strip()
        parts.append('## ' + heading + '\n' + (body or labels[8]))
    return '\n\n'.join(parts)


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
