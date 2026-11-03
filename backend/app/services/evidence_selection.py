"""Bounded evidence discovery. Ranking and quote matching are not semantic verification."""
import re
from collections import defaultdict

EVIDENCE_SELECTION_VERSION = 1
MAX_STORED_CHUNKS = 128
MAX_VECTOR_CHUNKS = 8
MAX_ANALYSIS_NEEDS = 5
MAX_TRIAGE_CANDIDATES = 24

_STOP = set("the a an and or of to in on for from with by is are was were this that what how does do can could should under which when between study research evidence question review literature method methods limitation limitations compare comparison"
            .split())


def query_terms(query, limit=24):
    """Unicode word tokens only, safe to bind as OR tsquery lexemes."""
    return list(dict.fromkeys(w for w in re.findall(r"[^\W_]+", str(query).casefold())
                              if len(w) >= 2 and w not in _STOP))[:limit]


def spread_indexes(count, limit):
    """Keep document order while sampling the whole bounded document, not just its preamble."""
    if count <= limit:
        return list(range(count))
    if limit <= 1:
        return [0] if limit else []
    return [i * (count - 1) // (limit - 1) for i in range(limit)]


def rank_discovery_candidates(items):
    """Prioritize title/abstract query overlap before bounded fetch, never certify relevance.

    Uncertain canonical/foundational titles are retained. Query balancing still
    happens afterwards, so a popular concept cannot consume the whole source cap.
    """
    def priority(item):
        queries = item.matched_queries or [item.query or ""]
        title = set(query_terms((item.title or "")[:500], limit=64))
        abstract = set(query_terms((item.content or "")[:4000], limit=256))
        scores = []
        for query in queries:
            terms = set(query_terms(query))
            scores.append((len(title & terms) * 3 + len(abstract & terms)) / max(1, len(terms)))
        return max(scores, default=0)
    return sorted(items, key=priority, reverse=True)


def metadata_triage_order(items, assessments, needs=None):
    """Apply provisional metadata judgments to supplied candidates, retaining uncertain items."""
    by_id = defaultdict(list)
    for assessment in assessments:
        by_id[assessment["candidate_id"]].append(assessment)
    allowed = {n["need_id"] for n in (needs or [])}
    foundations = {n["need_id"] for n in (needs or []) if n.get("role") == "FOUNDATION"}
    rows = []
    for i, item in enumerate(items):
        key = f"c{i+1:02d}"
        supplied = by_id.get(key, [])
        decision = supplied[0] if len(supplied) == 1 else {
            "candidate_id": key, "relevance": "UNCERTAIN", "study_role": "UNCERTAIN",
            "reason": "Missing or ambiguous metadata assessment",
        }
        hints = list(dict.fromkeys(n for n in decision.get("need_ids", [])
                     if n in allowed and decision["relevance"] == "DIRECT"
                     and (n not in foundations or decision["study_role"] == "PRIMARY")))
        rows.append({**decision, "need_ids": hints, "url": str(item.url), "title": item.title,
                     "fetch_url": str(getattr(item, "full_text_url", None) or item.url),
                     "metadata_assessment_present": len(supplied) == 1})

    def priority(index):
        decision = rows[index]
        if decision["relevance"] == "DIRECT":
            return {"PRIMARY": 0, "REVIEW": 1, "UNCERTAIN": 2, "GUIDE": 3}[decision["study_role"]]
        return {"UNCERTAIN": 2, "CONTEXT": 4, "OUT_OF_SCOPE": 5}[decision["relevance"]]

    # Candidates may share a landing URL but have different full-text locations.
    # Preserve assessment identity by supplied position, never by URL.
    return [items[index] for index in sorted(range(len(items)), key=priority)], rows


def balance_by_need(items, needs, decisions, candidate_key):
    """Use provisional direct need hints, retaining all remaining candidates.

    Discovery-query representation is not evidence of topical support. This
    ordering improves allocation within a cap; it does not certify coverage.
    """
    from app.services.research_quality import balance_by_query
    by_fetch = {d["fetch_url"]: d.get("need_ids", []) for d in (decisions or [])
                if d.get("fetch_url") and d.get("relevance") == "DIRECT"}
    return balance_by_query(items, [n["need_id"] for n in (needs or [])],
                            lambda item: by_fetch.get(candidate_key(item), []))


def fuse_diverse_chunks(vector_rows, lexical_rows, limit):
    """Reciprocal rank fusion, then one chunk per source before filling remaining slots.

    No irrelevant sequential fallback and no claimed cosine-confidence calibration.
    Both input lists must already have been restricted to the owning READY sources.
    """
    chunks, scores = {}, defaultdict(float)
    for rows in (vector_rows, lexical_rows):
        seen = set()
        for rank, (chunk, _score) in enumerate(rows, start=1):
            key = str(chunk.id)
            if key in seen:
                continue
            seen.add(key)
            chunks[key] = chunk
            scores[key] += 1 / (60 + rank)
    ranked = sorted(chunks, key=lambda key: (-scores[key], str(chunks[key].source_id), chunks[key].chunk_index, key))
    selected, source_ids = [], set()
    for key in ranked:
        if chunks[key].source_id not in source_ids:
            selected.append(key)
            source_ids.add(chunks[key].source_id)
        if len(selected) >= limit:
            break
    selected += [key for key in ranked if key not in selected][:max(0, limit-len(selected))]
    # Lower values rank first; this is a fused rank, NOT a cosine distance.
    return [(chunks[key], 1 / scores[key]) for key in selected[:limit]]


def analysis_needs(state):
    planned = (state.get("plan") or {}).get("evidence_needs") or []
    if planned:
        needs, seen = [], set()
        for i, item in enumerate(planned[:MAX_ANALYSIS_NEEDS]):
            need = dict(item)
            if not need.get("question", "").strip():
                continue
            key = str(need.get("need_id") or "")[:40]
            if not key or key in seen:
                base, suffix = f"need_{i+1}", 1
                key = base
                while key in seen:
                    key = f"{base}_{suffix}"
                    suffix += 1
            seen.add(key)
            needs.append({**need, "need_id": key})
        if needs:
            return needs
    queries = list(dict.fromkeys(state.get("current_queries") or []))
    if not queries:
        queries = [state.get("research_question") or ""]
    return [{"need_id": f"query_{i+1}", "question": q, "search_query": q, "section_id": "background"}
            for i, q in enumerate(queries[:MAX_ANALYSIS_NEEDS])]


def evidence_need_coverage(needs, results, proposed_counts=None):
    rows = []
    for i, need in enumerate(needs):
        claims, retrieved = results[i] if i < len(results) else ([], [])
        sources = sorted({str(c["source_id"]) for c in claims})
        row = {**need, "status": "QUOTE_BACKED_CANDIDATES" if claims else "NO_MATCHED_QUOTE",
                     "retrieved_sources": sorted({str(c.source_id) for c in retrieved}),
                     "source_ids": sources,
                     "distinct_quotes": len({(c["source_id"], c["evidence_quote"]) for c in claims})}
        if proposed_counts is not None:
            proposed = proposed_counts[i] if i < len(proposed_counts) else 0
            row.update(proposed_claims=proposed, rejected_or_duplicate_claims=max(0, proposed-len(claims)))
        rows.append(row)
    return {"version": EVIDENCE_SELECTION_VERSION,
            "scope": "retrieved quote candidates per planned need; not entailment, study quality or exhaustive coverage",
            "needs": rows, "missing_need_ids": [r["need_id"] for r in rows if not r["source_ids"]]}


def blocking_evidence_gaps(coverage):
    """Missing central support blocks delivery; a declared contextual gap can be a valid limit."""
    missing = set(coverage.get("missing_need_ids", []))
    rows = {r["need_id"]: r for r in coverage.get("needs", [])}
    return sorted(key for key in missing if key not in rows or
                  rows[key].get("role", "CORE_CONCEPT") in {"FOUNDATION", "CORE_CONCEPT", "COMPARISON"})
