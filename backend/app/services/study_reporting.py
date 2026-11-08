"""Conservative editorial flags, not proof of semantic support or study validity."""
import re
import unicodedata


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text)).lower()
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def _sentences(text):
    return re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-Ỹ])|\n|;\s*|\bbut\b|\bhowever\b', text)


def _asserted(sentence):
    text = _fold(sentence)
    # A denial or future proposal is not a completed method. Limit these checks
    # to the method-action clause so an unrelated "no missing data" is harmless.
    action = r'(?:adapt\w*|validat\w*|pilot.test\w*|dieu chinh|kiem dinh|tham dinh)'
    if re.search(r'\b(?:not|never|no|without|khong|chua)\b[^.;]{0,45}' + action, text):
        return False
    if re.search(r'\b(?:will|would|could|should|future|proposed|plan to|se|du kien|de xuat)\b', text):
        return False
    prior = re.search(r'\b(?:prior|previous|published|earlier|cited)\b|et al\b|nghien cuu truoc', text)
    own = re.search(r'\b(?:we|our|this study|these items|by us)\b|nghien cuu nay|chung toi', text)
    return not prior or bool(own)


def _adaptation(text):
    text = _fold(text)
    return bool(re.search(r'\b(?:instrument|questionnaire|scale|items?)\b|thang do|bang hoi', text)
                and re.search(r'\b(?:adapted|derived|borrowed)\b|dieu chinh tu|chuyen the tu', text))


def _validation(text):
    text = _fold(text)
    return bool(re.search(r'\b(?:we|our study|this study)\b[^.;]{0,40}\b(?:validated|pilot.tested)\b|'
                          r'\b(?:instrument|questionnaire|scale|items?)\b[^.;]{0,35}\b(?:was|were|has been)\s+(?:empirically\s+)?validated\b|'
                          r'(?:chung toi|nghien cuu nay)[^.;]{0,40}(?:kiem dinh|tham dinh).*thang do', text))


def study_reporting_findings(markdown, contract, context):
    sections = {}
    for section in contract.get('sections', []):
        match = re.search(rf'(?ms)^##\s+{re.escape(section["heading"])}\s*\n(.*?)(?=^##\s|\Z)', markdown)
        if match:
            sections[section['id']] = match[1]
    findings = []
    gap_text = '\n'.join(sections.get(key, '') for key in ('introduction', 'related_work', 'discussion', 'conclusion'))
    for sentence in _sentences(gap_text):
        value = _fold(sentence)
        unbounded = re.search(r'\b(?:no (?:prior|previous|existing|published) (?:studies|research|work)|(?:the )?literature lacks|first (?:study|research)|no study has)\b|chua co nghien cuu nao', value)
        bounded = re.search(r'\b(?:retrieved|reviewed|included|searched|our corpus|this corpus|search scope)\b|trong pham vi|tai lieu da thu thap', value)
        denied = re.search(r'\b(?:not claim|cannot claim|do not claim)\b|\b(?:not|never|cannot)\b.{0,20}\bfirst\b|khong khang dinh', value)
        if unbounded and not bounded and not denied:
            findings.append({'code': 'UNBOUNDED_RESEARCH_GAP', 'message': 'Scope absence/novelty claims to the searched corpus; missing retrieved evidence does not establish a field-wide research gap.'})
            break
    if contract.get('article_type') != 'EMPIRICAL_STUDY':
        return findings
    provenance = '\n'.join(str(v) for v in (context.get('study_method_provenance') or {}).values())
    provenance_sentences = _sentences(provenance)
    own_methods = '\n'.join(sections.get(key, '') for key in ('abstract', 'methods'))
    for code, detect in (('UNRECORDED_INSTRUMENT_ADAPTATION', _adaptation), ('UNRECORDED_INSTRUMENT_VALIDATION', _validation)):
        # Only researcher-supplied method/provenance counts here. Citations and
        # proposed protocols cannot attest that the current study did the work.
        recorded = any(_asserted(s) and detect(s) for s in provenance_sentences)
        if not recorded and any(_asserted(s) and detect(s) for s in _sentences(own_methods)):
            findings.append({'code': code, 'message': 'The manuscript claims instrument adaptation/validation absent from user method records. Remove the assertion or obtain explicit provenance; cited methods do not establish this study performed them.'})
    return findings
