"""Conservative formatting of known source metadata; no bibliographic enrichment."""
import re
from html import unescape


def _text(value) -> str:
    return " ".join(unescape(str(value or "")).split())


def reference_identity(item: dict) -> str:
    return str(item.get("source_id") or item.get("source_url") or item.get("claim_id"))


def _parts(item: dict) -> tuple[str, str, str, str, str, str]:
    title = _text(item.get("source_title") or item.get("source_url") or item.get("source_tag") or "Untitled")
    author = _text(item.get("source_author"))
    match = re.search(r"\b(?:19|20)\d{2}\b", _text(item.get("publication_date")))
    return (title, author, match[0] if match else "n.d.", _text(item.get("source_url")),
            _text(item.get("venue")), _text(item.get("doi")))


def _label_identity(item: dict) -> tuple[str, str]:
    title, author, year, _, _, _ = _parts(item)
    return (author or title)[:470], year


def reference_suffixes(items: list[dict], style: str) -> dict[str, str]:
    """Disambiguate actual rendered author-date labels, once per source.

    Stable first-citation order avoids deriving surname/name structure from an
    unstructured author field. This is a product citation style, not full APA.
    """
    if style == "IEEE":
        return {}
    groups: dict[tuple[str, str], list[str]] = {}
    for item in items:
        identity = reference_identity(item)
        group = groups.setdefault(_label_identity(item), [])
        if identity not in group:
            group.append(identity)
    def suffix(index):
        result = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(97 + remainder) + result
        return result
    return {identity: suffix(index) for group in groups.values() if len(group) > 1
            for index, identity in enumerate(group, 1)}


def format_reference(item: dict, number: int, style: str, *, suffix: str = "") -> tuple[str, str]:
    title, author, year, url, venue, doi = _parts(item)
    if style == "IEEE":
        pieces = [author, f'“{title}”', venue, year if year != "n.d." else ""]
        text = ", ".join(piece for piece in pieces if piece)
        return f"[{number}]", f"[{number}] {text}." + (f" DOI: https://doi.org/{doi}." if doi else (f" [Online]. Available: {url}" if url else ""))
    date = year + suffix
    identity = author or title
    label = f"({identity[:470]}, {date})"
    if style == "APA":
        locator = f" https://doi.org/{doi}" if doi else (f" {url}" if url else "")
        return label, f"{identity}. ({date}). " + (f"{title}. " if author else "") + (f"{venue}. " if venue else "") + locator
    # An actual access date is not recorded in the source snapshot. Do not
    # substitute the current export date or fabricate publication metadata.
    locator = f"DOI: https://doi.org/{doi}" if doi else (f"[Online]. {url}" if url else "")
    return label, f"{identity} ({date}) " + (f"{title}. " if author else "") + (f"{venue}. " if venue else "") + locator


def reference_metadata_notes(items: list[dict]) -> list[dict]:
    notes, seen = [], set()
    for item in items:
        identity = reference_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        title, author, year, url, venue, doi = _parts(item)
        missing = []
        if not item.get("source_title"):
            missing.append("title")
        if not author:
            missing.append("author")
        if year == "n.d.":
            missing.append("publication_year")
        if not url:
            missing.append("url")
        if item.get("source_type") == "PAPER" and not doi:
            missing.append("doi")
        if item.get("source_type") == "PAPER" and not venue:
            missing.append("venue")
        if missing:
            notes.append({"source_id": item.get("source_id"), "missing": missing})
    return notes
