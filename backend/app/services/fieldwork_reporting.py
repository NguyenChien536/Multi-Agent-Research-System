"""Conservative checks for labeled CSV summary tables, not free-text entailment."""
import math
import re


def numeric_table_mismatches(markdown: str, summary: dict) -> list[str]:
    columns = summary.get('columns') or {}
    findings = []
    headers = []
    for line in markdown.splitlines():
        if not line.lstrip().startswith('|'):
            headers = []
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-+:?', cell) for cell in cells):
            continue
        matched = [(name, stats) for name, stats in columns.items()
                   if any(re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', cell) for cell in cells)]
        if not headers:
            headers = cells
            continue
        if len(matched) != 1 or len(cells) != len(headers):
            continue
        name, stats = matched[0]
        for heading, cell in zip(headers, cells):
            label = heading.lower()
            if 'distribution' in label or 'frequency' in label or 'frequencies' in label:
                pairs = re.findall(r'([-+]?\d+(?:\.\d+)?)\s*:\s*(\d+)\b', cell)
                expected = stats.get('value_counts')
                if pairs and expected is not None:
                    actual = {str(float(value)): int(count) for value, count in pairs}
                    if len(actual) != len(pairs) or actual != expected:
                        findings.append(f'{name}: reported frequencies differ from uploaded CSV counts.')
                continue
            key = ('mean' if re.search(r'\bmean\b|average', label) else
                   'minimum' if 'minimum' in label else 'maximum' if 'maximum' in label else
                   ('population_sd' if 'population' in label else 'sample_sd')
                   if re.search(r'\bsd\b|standard deviation', label) else None)
            if key is None or stats.get(key) is None:
                continue
            # Only compare a cell containing a single number; never infer what
            # intervals, formulas, footnotes or multiple values mean.
            plain = cell.replace('$', '').replace('*', '').strip()
            number = re.fullmatch(r'([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)', plain)
            if not number:
                continue
            raw = number[1]
            mantissa, _, exponent = raw.lower().partition('e')
            if len(exponent.lstrip('+-')) > 4 or not math.isfinite(float(raw)):
                findings.append(f'{name}: reported {key} is not a finite supported value.')
                continue
            decimals = len(mantissa.partition('.')[2])
            tolerance = .5 * 10 ** (int(exponent or 0) - decimals) + 1e-10
            if not math.isclose(float(raw), stats[key], rel_tol=1e-9, abs_tol=tolerance):
                findings.append(f'{name}: reported {key} differs from the computed CSV value.')
    return list(dict.fromkeys(findings))
