"""Deterministic collection balance and conservative research-quality checks."""
import re

LEDGER_LABELS = {
    "en": ("Recorded search activity", "Narrative collection without systematic screening. Counts are records per request, not unique screened studies. No publication-year restriction is assumed unless recorded in the filters."),
    "vi": ("Nhật ký tìm kiếm đã thực hiện", "Thu thập tường thuật, chưa sàng lọc tổng quan hệ thống. Số lượng là bản ghi theo từng truy vấn, không phải số nghiên cứu độc lập. Chỉ ghi giới hạn năm xuất bản nếu có trong bộ lọc."),
    "fr": ("Journal des recherches exécutées", "Collecte narrative sans sélection systématique. Les nombres sont des résultats par requête, pas des études distinctes sélectionnées. Une restriction d’année doit être explicitement enregistrée dans les filtres."),
    "de": ("Protokoll der ausgeführten Suche", "Narrative Sammlung ohne systematisches Screening. Die Zahlen beziehen sich auf Datensätze pro Anfrage, nicht auf unabhängig geprüfte Studien. Ein Publikationszeitraum gilt nur bei dokumentiertem Filter."),
    "es": ("Registro de búsquedas realizadas", "Recopilación narrativa sin cribado sistemático. Las cifras son registros por consulta, no estudios únicos evaluados. Un límite de año de publicación solo se aplica si está registrado en los filtros."),
    "ja": ("実行した検索の記録", "系統的なスクリーニングを行わない文献収集である。件数は検索ごとのレコード数であり、独立して評価した研究数ではない。出版年の制限はフィルターに記録された場合のみ適用する。"),
    "zh": ("实际检索记录", "本研究进行叙述性文献收集，未实施系统筛选。数量指每次查询返回的记录，不代表独立筛选的研究。出版年份限制仅在筛选参数明确记录时适用。"),
    "ko": ("실행한 검색 기록", "체계적 선별 없이 문헌을 수집하였다. 수치는 쿼리별 반환 레코드 수이며 독립적으로 평가한 연구 수가 아니다. 출판 연도 제한은 필터에 명시된 경우에만 적용한다."),
}
LEDGER_HEADINGS = [value[0] for value in LEDGER_LABELS.values()]
LEDGER_COLUMNS = {
    "en": ("Provider", "Exact query", "Executed at", "Filters", "Status", "Counts: candidates / duplicates / fetched / accepted"),
    "vi": ("Dịch vụ", "Truy vấn chính xác", "Thời điểm chạy", "Bộ lọc", "Trạng thái", "Số lượng: ứng viên / trùng / tải được / giữ lại"),
    "fr": ("Fournisseur", "Requête exacte", "Date d’exécution", "Filtres", "État", "Nombres : candidats / doublons / récupérés / retenus"),
    "de": ("Anbieter", "Exakte Suchanfrage", "Ausgeführt am", "Filter", "Status", "Anzahl: Kandidaten / Duplikate / abgerufen / übernommen"),
    "es": ("Proveedor", "Consulta exacta", "Fecha de ejecución", "Filtros", "Estado", "Cantidades: candidatos / duplicados / recuperados / aceptados"),
    "ja": ("サービス", "正確な検索式", "実行時刻", "フィルター", "状態", "件数：候補 / 重複 / 取得 / 採用"),
    "zh": ("服务", "完整查询", "执行时间", "筛选参数", "状态", "数量：候选 / 重复 / 获取 / 纳入"),
    "ko": ("제공자", "정확한 검색어", "실행 시각", "필터", "상태", "건수: 후보 / 중복 / 수집 / 채택"),
}
LEDGER_PATTERN = r"(?ms)^### (?:" + "|".join(re.escape(h) for h in LEDGER_HEADINGS) + r")\s*\n.*?(?=^### |\Z)"


def bounded_quality_batches(sections, max_chars=2600, max_passages=12):
    batches, names, content, count = [], [], "", 0
    for name, body in sections:
        for paragraph in body.split("\n\n"):
            if not paragraph.strip():
                continue
            block = f"## {name}\n{paragraph}"
            if content and (len(content) + len(block) + 2 > max_chars or count >= max_passages):
                batches.append((names, content))
                names, content, count = [], "", 0
            if name not in names:
                names.append(name)
            content += ("\n\n" if content else "") + block
            count += 1
    if content:
        batches.append((names, content))
    return batches


def balance_by_query(items, queries, query_getter):
    """Round-robin ranked candidates; one candidate is returned only once."""
    groups = {q: [] for q in dict.fromkeys(queries)}
    for index, item in enumerate(items):
        for query in query_getter(item):
            if query in groups:
                groups[query].append(index)
    selected, ordered = set(), []
    while True:
        changed = False
        for indexes in groups.values():
            while indexes and indexes[0] in selected:
                indexes.pop(0)
            if indexes:
                index = indexes.pop(0)
                selected.add(index)
                ordered.append(items[index])
                changed = True
        if not changed:
            break
    return ordered + [item for i, item in enumerate(items) if i not in selected]


def unique_quote_claims(claims):
    """Do not count paraphrases/translations of the same quote as new evidence."""
    result, first_by_key = [], {}
    for item in claims:
        quote = item.get("evidence_quote") or item.get("evidence_text")
        key = (item.get("source_id"), " ".join(str(quote or "").split()))
        if not quote or not item.get("source_id"):
            result.append(item)
            continue
        if key not in first_by_key:
            first_by_key[key] = {**item, "related_claims": []}
            result.append(first_by_key[key])
        wording = item.get("claim") or item.get("claim_text")
        if wording and wording not in first_by_key[key]["related_claims"]:
            first_by_key[key]["related_claims"].append(wording)
    return result


def canonicalize_quote_markers(markdown, claims):
    canonical = {}
    for item in claims:
        quote = item.get("evidence_quote") or item.get("evidence_text")
        if not quote or not item.get("source_id") or not item.get("claim_id"):
            continue
        key = (item["source_id"], " ".join(quote.split()))
        first = canonical.setdefault(key, str(item["claim_id"]))
        markdown = markdown.replace(f"[[@claim:{item['claim_id']}]]", f"[[@claim:{first}]]")
    return re.sub(r"(\[\[@claim:[^\]]+\]\])(?:\s*[,;]?\s*\1)+", r"\1", markdown)


def query_coverage(state):
    queries = list(dict.fromkeys((state.get("plan") or {}).get("search_queries", [])))
    sources = state.get("collected_sources") or []
    rows = []
    for query in queries:
        matched = [s for s in sources if query in (s.get("discovery_queries") or [s.get("query")])]
        rows.append({"query": query, "accepted_sources": len(matched),
                     "source_ids": [s.get("db_id") for s in matched if s.get("db_id")]})
    return {"queries": rows, "missing_queries": [r["query"] for r in rows if not r["accepted_sources"]],
            "scope": "discovery-query coverage proxy; not semantic relevance or exhaustive topic coverage"}


def guarantee_risks(text):
    """Flag strong assertions for extra review, not decide whether a theorem is true."""
    text = re.sub(r"\[\[@claim:[^\]]+\]\]", "", text)
    risks = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        lowered = sentence.casefold()
        if not re.search(r"\b(guarantee[sd]|ensures?|preserv(?:e[sd]?|ing)|prove[sn]?|robust|pareto.optimal|globally.optimal|resolves?)\b|bảo đảm|đảm bảo|chứng minh|bảo toàn|giải quyết được", lowered):
            continue
        if re.search(r"\b(may|might|could|hypothes\w*|propos\w*|requires? validation|not|no|lack\w*|without|cannot|future|potential|research direction)\b|chưa|có thể|giả thuyết|không", lowered):
            continue
        risks.append(sentence[:500])
    return risks


def search_ledger_section(state):
    """Render actual execution data without invented screening counts or criteria."""
    activity = state.get("search_activity") or []
    locale = str(state.get("language", "en")).lower().split("-")[0]
    heading, intro = LEDGER_LABELS.get(locale, LEDGER_LABELS["en"])
    columns = LEDGER_COLUMNS.get(locale, LEDGER_COLUMNS["en"])
    def cell(value):
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    rows = [f"### {heading}", "", intro, "", "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |"]
    import json
    for event in activity:
        rows.append("| " + " | ".join(cell(v) for v in (
            event.get("provider"), event.get("query") or "; ".join(event.get("queries", [])),
            event.get("executed_at") or event.get("completed_at"),
            json.dumps(event.get("filters", {}), ensure_ascii=False), event.get("status"),
            " / ".join(cell(event.get(key)) for key in ("candidate_count", "duplicate_count", "fetched_count", "accepted_count"))
        )) + " |")
    return "\n".join(rows)


def inject_search_ledger(markdown, state):
    contract = (state.get("plan") or {}).get("manuscript_contract") or {}
    if not contract.get("research_quality_policy") or state.get("editorial_revision") or not state.get("search_activity"):
        return markdown
    section = next((s["heading"] for s in contract.get("sections", []) if s["id"] == "review_methods"), None)
    if not section:
        return markdown
    pattern = rf"(?ms)(^##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)"
    def replace(match):
        body = re.sub(LEDGER_PATTERN, "", match[2]).rstrip()
        return match[1] + body + "\n\n" + search_ledger_section(state) + "\n\n"
    return re.sub(pattern, replace, markdown)
