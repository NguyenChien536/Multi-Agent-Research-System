"""Observable manuscript hierarchy checks; never a substitute for semantic review."""
import re
from dataclasses import dataclass


@dataclass
class Heading:
    level: int
    title: str
    body: str
    children: list


def strip_fenced_blocks(markdown):
    """CommonMark-style fences: up to three spaces, same marker, >= opening length.

    An unclosed fence consumes the rest of the document. Code examples must not
    masquerade as real paper sections just because the closing fence is missing.
    """
    lines, marker, length = [], None, 0
    for line in markdown.splitlines():
        if marker is None:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if opening:
                marker, length = opening[1][0], len(opening[1])
                lines.append("")
            else:
                lines.append(line)
        elif re.fullmatch(r" {0,3}" + re.escape(marker) + "{" + str(length) + r",}\s*", line):
            marker = None
            lines.append("")
    return "\n".join(lines)


def heading_tree(markdown: str) -> tuple[str, list[Heading]]:
    # Ignore fenced code so examples inside a code block cannot become sections.
    text = strip_fenced_blocks(markdown)
    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
    roots, stack = [], []
    for i, match in enumerate(matches):
        node = Heading(len(match[1]), match[2].strip(),
            text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip(), [])
        while stack and stack[-1].level >= node.level:
            stack.pop()
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    return (text[:matches[0].start()].strip() if matches else text.strip()), roots


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.children)


def narrative(node, excluded_titles=()):
    if node.title in excluded_titles:
        return ""
    return "\n\n".join(part for part in [node.body, *(narrative(child, excluded_titles) for child in node.children)] if part)


def prose_text(text):
    text = re.sub(r"\[\[@claim:[^\]]*\]\]", "", text)
    text = re.sub(r"(?m)^\s*(?:\||!\[|\[\[figure:).*$", "", text)
    return text.strip()


def review_sections(markdown, max_chars=5000):
    """Emit actual prose once per location, never a synthetic empty-title passage.

    Structural emptiness belongs to deterministic validation. A heading with
    subsections can legitimately have no direct introductory paragraph.
    """
    preamble, roots = heading_tree(markdown)
    sections = [("Preamble" if roots else "Full report", preamble)] if preamble else []
    def collect(nodes, parents=()):
        for node in nodes:
            scope = parents + (node.title,) if node.level >= 3 else (node.title,)
            if node.body:
                sections.append((" / ".join(scope), node.body))
            collect(node.children, scope if node.level >= 2 else ())
    collect(roots)
    chunks = []
    for heading, body in sections:
        while len(body) > max_chars:
            split_at = body.rfind("\n", 0, max_chars)
            if split_at < max_chars // 2:
                split_at = max_chars
            chunks.append((heading, body[:split_at].strip()))
            body = body[split_at:].strip()
        if body:
            chunks.append((heading, body))
    return chunks


def validate_hierarchy(markdown, contract):
    policy = (contract or {}).get("structure_policy")
    if not policy:
        return []  # Frozen historical manuscripts keep their recorded policy.
    from app.services.manuscript import _heading_key
    from app.services.research_quality import LEDGER_HEADINGS
    _, roots = heading_tree(markdown)
    findings = []
    def add(code, message):
        findings.append({"code": code, "message": message})
    for node in walk(roots):
        if node.level >= 3 and node.title not in LEDGER_HEADINGS and not narrative(node, LEDGER_HEADINGS).strip():
            add("EMPTY_SUBSECTION", f"Develop or remove the empty subsection '{node.title}'.")
        if any(child.level != node.level + 1 for child in node.children):
            add("HEADING_DEPTH", f"Do not skip heading levels below '{node.title}'.")
    sections = {_heading_key(node.title): node for node in walk(roots) if node.level == 2}
    for section in contract["sections"]:
        rule = policy["sections"].get(section["id"])
        node = sections.get(_heading_key(section["heading"]))
        if not rule or not node:
            continue
        children = [child for child in node.children if child.level == 3 and child.title not in LEDGER_HEADINGS]
        for child in children:
            # Citation IDs, tables and figure assets cannot stand in for prose.
            prose = prose_text(narrative(child, LEDGER_HEADINGS))
            if len(prose) < policy["minimum_subsection_prose_characters"]:
                add("UNDEVELOPED_SUBSECTION", f"Explain the evidence and interpretation in '{child.title}' using substantive prose.")
        # Compact papers should not be fragmented just to satisfy a heading count.
        if len(prose_text(narrative(node, LEDGER_HEADINGS))) < policy["expand_after_characters"]:
            continue
        if len(children) < rule["minimum_subsections"]:
            add("SUBSECTION_STRUCTURE", f"Organize '{node.title}' into at least {rule['minimum_subsections']} meaningful H3 subsections: {rule['purpose']}.")
        names = [_heading_key(child.title) for child in children]
        if len(names) != len(set(names)):
            add("DUPLICATE_SUBSECTION", f"Use distinct analytical subsection titles within '{node.title}'.")
        if len(children) > policy["maximum_subsections"]:
            add("FRAGMENTED_SECTION", f"Consolidate excessive subsections in '{node.title}' around the main argument.")
    return findings
