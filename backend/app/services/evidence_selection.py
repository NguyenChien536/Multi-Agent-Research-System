"""Bounded evidence discovery. Ranking and quote matching are not semantic verification."""
import re
from collections import defaultdict

EVIDENCE_SELECTION_VERSION = 1
MAX_STORED_CHUNKS = 128
MAX_VECTOR_CHUNKS = 8
MAX_ANALYSIS_NEEDS = 5

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
                key = f"need_{i+1}"
            seen.add(key)
            needs.append({**need, "need_id": key})
        if needs:
            return needs
    queries = list(dict.fromkeys(state.get("current_queries") or []))
    if not queries:
        queries = [state.get("research_question") or ""]
    return [{"need_id": f"query_{i+1}", "question": q, "search_query": q, "section_id": "background"}
            for i, q in enumerate(queries[:MAX_ANALYSIS_NEEDS])]


def evidence_need_coverage(needs, results):
    rows = []
    for need, (claims, retrieved) in zip(needs, results):
        sources = sorted({str(c["source_id"]) for c in claims})
        rows.append({**need, "status": "QUOTE_BACKED_CANDIDATES" if claims else "NO_MATCHED_QUOTE",
                     "retrieved_sources": sorted({str(c.source_id) for c in retrieved}),
                     "source_ids": sources,
                     "distinct_quotes": len({(c["source_id"], c["evidence_quote"]) for c in claims})})
    return {"version": EVIDENCE_SELECTION_VERSION,
            "scope": "retrieved quote candidates per planned need; not entailment, study quality or exhaustive coverage",
            "needs": rows, "missing_need_ids": [r["need_id"] for r in rows if not r["source_ids"]]}


def blocking_evidence_gaps(coverage):
    """Missing central support blocks delivery; a declared contextual gap can be a valid limit."""
    missing = set(coverage.get("missing_need_ids", []))
    rows = {r["need_id"]: r for r in coverage.get("needs", [])}
    return sorted(key for key in missing if key not in rows or
                  rows[key].get("role", "CORE_CONCEPT") in {"CORE_CONCEPT", "COMPARISON"})
