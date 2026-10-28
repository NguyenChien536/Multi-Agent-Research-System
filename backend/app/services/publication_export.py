"""Publication source bundles using official TeX classes, with escaped content only.

No compiler, shell command, remote fetch or model-generated TeX is executed here.
"""
import io
import json
import re
import zipfile
from urllib.parse import quote, urlsplit

TEMPLATES = {
    "IEEE_CONFERENCE": {"class": "IEEEtran", "options": "conference", "source": "https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/"},
    "ACM_SIGCONF": {"class": "acmart", "options": "sigconf,nonacm", "source": "https://www.acm.org/publications/proceedings-template"},
}


def tex_escape(text) -> str:
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in str(text))


def _inline(text, labels):
    result = []
    for part in re.split(r"(\$[^$\n]+\$|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\d+\])", text):
        if part in labels:
            result.append(r"\cite{" + labels[part] + "}")
        elif part.startswith("$") and part.endswith("$"):
            commands = set(re.findall(r"\\([A-Za-z]+)", part))
            allowed = {"frac", "sqrt", "sum", "prod", "min", "max", "arg", "log", "exp", "alpha", "beta", "gamma", "delta", "sigma", "mu", "theta", "lambda", "epsilon", "Delta", "Sigma", "in", "leq", "geq", "neq", "times", "cdot", "mathrm", "mathbf", "text", "left", "right", "lVert", "rVert", "infty"}
            safe = len(part) <= 500 and commands <= allowed and part.count("{") == part.count("}") and not re.search(r"[%#&]", part)
            result.append(part if safe else tex_escape(part))
        elif part.startswith("**") and part.endswith("**"):
            result.append(r"\textbf{" + tex_escape(part[2:-2]) + "}")
        elif part.startswith("*") and part.endswith("*"):
            result.append(r"\emph{" + tex_escape(part[1:-1]) + "}")
        elif part.startswith("`") and part.endswith("`"):
            result.append(r"\texttt{" + tex_escape(part[1:-1]) + "}")
        elif (match := re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", part)):
            parsed = urlsplit(match[2])
            if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
                result.append(r"\href{" + tex_escape(match[2]) + "}{" + tex_escape(match[1]) + "}")
            else:
                result.append(tex_escape(match[1]))
        else:
            # Author-date labels are also replaced using persisted citation metadata.
            escaped = tex_escape(part)
            for label, key in labels.items():
                if not re.fullmatch(r"\[\d+\]", label):
                    escaped = escaped.replace(tex_escape(label), r"\cite{" + key + "}")
            result.append(escaped)
    return "".join(result)


def build_publication_bundle(title: str, markdown: str, metadata: dict, citations: list[dict], template: str,
                             *, version_id: str, version_number: int) -> tuple[bytes, dict]:
    if template not in TEMPLATES:
        raise ValueError("Unsupported publication template")
    if len(markdown.encode()) > 2_000_000:
        raise ValueError("Manuscript exceeds export size limit")
    profile = TEMPLATES[template]
    contract = metadata.get("manuscript_contract") or {}
    headings = {item["id"]: item["heading"] for item in contract.get("sections", [])}
    figures = metadata.get("scientific_figures") or []
    figures_by_id = {f["id"]: f for f in figures}
    # Fixed identifiers prevent zip path traversal and arbitrary TeX input paths.
    if any(not re.fullmatch(r"(?:workflow|evaluation)", key) for key in figures_by_id):
        raise ValueError("Unknown scientific figure")
    labels, bibliography, seen = {}, [], {}
    for item in citations:
        identity = item.get("source_id") or item.get("source_url") or item.get("source_title")
        if identity not in seen:
            key = f"ref{len(seen)+1}"
            seen[identity] = key
            text = ". ".join(str(item[k]) for k in ("source_author", "source_title", "publication_date") if item.get(k))
            url = str(item.get("source_url") or "")
            parsed = urlsplit(url)
            # URL-aware line breaking avoids overflowing narrow publication columns.
            # Encoding braces/backslashes prevents a URL from becoming TeX source.
            url_tex = r". \url{" + quote(url, safe="/:?-._~=&") + "}" if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username else ""
            bibliography.append(r"\bibitem{" + key + "}" + tex_escape(text) + url_tex)
        if item.get("citation_label"):
            labels[item["citation_label"]] = seen[identity]
    sections = re.split(r"(?m)^##\s+(.+?)\s*$", markdown)
    abstract, keywords, body = "", "", []
    if len(sections) == 1:
        body.append(tex_escape(re.sub(r"(?m)^#\s+.*$", "", markdown)))
    reference_heading = contract.get("references_heading", "References")
    for index in range(1, len(sections), 2):
        heading, text = sections[index].strip(), sections[index + 1].strip()
        if heading in {headings.get("abstract"), "Abstract", "Tóm tắt"}:
            abstract = _inline(text, labels)
            continue
        if heading in {headings.get("keywords"), "Keywords", "Từ khóa"}:
            keywords = _inline(text, labels)
            continue
        if heading in {reference_heading, "References", "Tài liệu tham khảo"}:
            continue
        body.append(r"\section{" + tex_escape(heading) + "}")
        lines = text.splitlines(); in_list = False; in_code = False; table_rows = []
        def flush_table():
            if not table_rows:
                return
            ncols = max(len(row) for row in table_rows)
            if ncols > 8 or len(table_rows) > 40:
                raise ValueError("Table exceeds supported publication layout; split it into smaller tables")
            env = "table*" if ncols >= 4 else "table"
            width = r"\textwidth" if ncols >= 4 else r"\linewidth"
            body.extend([r"\begin{" + env + r"}[tb]\centering", r"\caption{Reported comparison; interpretation and data provenance are given in the text.}",
                         r"\begin{tabularx}{" + width + r"}{" + "X" * ncols + r"}\hline"])
            for row in table_rows:
                body.append(" & ".join(_inline(cell, labels) for cell in row + [""] * (ncols - len(row))) + r" \\")
            body.extend([r"\hline\end{tabularx}", r"\end{" + env + "}"])
            table_rows.clear()
        for line in lines:
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                # Render code as escaped text, never a raw verbatim/TeX escape route.
                body.append(r"\noindent\texttt{" + tex_escape(line) + r"}\par")
                continue
            if line.strip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    table_rows.append(cells)
                continue
            flush_table()
            image = re.fullmatch(r"!\[.*\]\(figures/([a-z_-]+)\.svg\)", line.strip())
            is_item = re.match(r"\s*(?:[-*+]\s+|\d+[.)]\s+)(.*)", line)
            if not is_item and in_list:
                body.append(r"\end{itemize}"); in_list = False
            if image:
                fig = figures_by_id.get(image[1])
                if fig is None:
                    raise ValueError("Manuscript references an unavailable figure")
                body += [r"\begin{figure}[htbp]\centering", r"\input{figures/" + image[1] + ".tex}",
                         r"\caption{" + tex_escape(fig["caption"]) + r"}\label{fig:" + image[1] + "}", r"\end{figure}"]
            elif line.startswith("### "):
                body.append(r"\subsection{" + tex_escape(line[4:]) + "}")
            elif line.startswith("#### "):
                body.append(r"\subsubsection{" + tex_escape(line[5:]) + "}")
            elif is_item:
                if not in_list:
                    body.append(r"\begin{itemize}"); in_list = True
                body.append(r"\item " + _inline(is_item[1], labels))
            elif line.strip() != "---":
                body.append(_inline(line, labels))
        flush_table()
        if in_list:
            body.append(r"\end{itemize}")
    preamble = [r"\documentclass[" + profile["options"] + "]{" + profile["class"] + "}",
                r"\usepackage{fontspec}",
                r"\usepackage{amsmath,graphicx,tikz,pgfplots,tabularx,flafter}", r"\pgfplotsset{compat=1.18}"]
    if template == "IEEE_CONFERENCE":
        preamble += [r"\setmainfont{texgyretermes-regular.otf}[BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf]", r"\usepackage{cite}", r"\usepackage{hyperref}"]
    else:
        preamble += [r"\settopmatter{printacmref=false}", r"\setcopyright{none}",
                     r"\acmConference{}{}{}", r"\acmDOI{}\acmISBN{}", r"\citestyle{acmnumeric}"]
    preamble += [r"\hypersetup{hidelinks}", r"\title{" + tex_escape(title) + "}", r"\author{Anonymous draft}", r"\begin{document}"]
    if template == "IEEE_CONFERENCE":
        front = [r"\maketitle", r"\begin{abstract}" + abstract + r"\end{abstract}", r"\begin{IEEEkeywords}" + keywords + r"\end{IEEEkeywords}"]
    else:
        front = [r"\begin{abstract}" + abstract + r"\end{abstract}", r"\keywords{" + keywords + "}", r"\maketitle"]
    tex = "\n".join(preamble + front + body + [r"\begin{thebibliography}{99}"] + bibliography + [r"\end{thebibliography}", r"\end{document}"])
    manifest = {"report_version_id": version_id, "version_number": version_number, "template": template,
                "official_template_source": profile["source"], "manuscript_contract": contract,
                "review_status": metadata.get("status", "NEEDS_REVIEW"),
                "scientific_context": metadata.get("scientific_context", {}), "method_provenance": metadata.get("method_provenance", {}),
                "figures": [{k: v for k, v in f.items() if k not in {"svg", "latex"}} for f in figures]}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("main.tex", tex)
        archive.writestr("manuscript.md", markdown)
        archive.writestr("provenance.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        # Figure TeX is reconstructed from validated server data, never executed
        # from arbitrary model/user-generated source.
        from app.services.scientific_paper import build_scientific_figures
        approved = [f for f in build_scientific_figures(manifest["scientific_context"], manifest["method_provenance"]) if f["id"] in figures_by_id]
        if set(figures_by_id) != {f["id"] for f in approved}:
            raise ValueError("Figure snapshot does not match the version's measured/conceptual provenance")
        for figure in approved:
            archive.writestr(f"figures/{figure['id']}.svg", figure["svg"])
            archive.writestr(f"figures/{figure['id']}.tex", figure["latex"])
            if figure.get("data"):
                archive.writestr(f"figures/{figure['id']}.json", json.dumps(figure["data"], indent=2))
        archive.writestr("README.md", f"# Publication source\n\nTemplate: {template}, official class `{profile['class']}`.\n\nCompile with `latexmk -xelatex -no-shell-escape main.tex` using a full TeX Live installation (IEEEtran/acmart, TikZ, pgfplots, TeX Gyre fonts), or import into Overleaf and select XeLaTeX.\n\nThis is an anonymous AI-assisted draft, not an accepted paper. Supply real author/affiliation information and follow the exact target venue instructions. No DOI, acceptance, publication date, statistical test or experimental result is invented. Review status: {manifest['review_status']}. Existing manuscript content is preserved; export does not upgrade its scientific validity.\n")
    return stream.getvalue(), manifest
