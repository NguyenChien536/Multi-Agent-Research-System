"""Pinned, local retrieval over a case's frozen snapshots; no embeddings/network."""
import math
import re
from collections import Counter

from sqlalchemy import select

from app.models.source import DocumentChunk
from app.tools.search_models import SearchResult

RETRIEVAL_PROFILE = "frozen-lexical-v1-1024-128"


def tokens(text):
    return Counter(re.findall(r"\w+", text.casefold()))


def rank(query, items, text, identity):
    query = tokens(query)
    def key(item):
        terms = tokens(text(item))
        score = sum(min(count, terms[t]) for t, count in query.items()) / math.sqrt(max(1, sum(terms.values())))
        return -score, identity(item)
    return sorted(items, key=key)


def chunks(text):
    for start in range(0, len(text), 896):
        yield text[start:start + 1024]
        if start + 1024 >= len(text):
            break


class FrozenCorpus:
    def __init__(self, sources, source_ids, trace):
        self.sources = {key: sources[key] for key in sorted(source_ids)}
        if any(len(s["text"]) > 200_000 for s in self.sources.values()):
            raise ValueError("Executor supports at most 200,000 characters per source; curate before freezing")
        self.urls = {s["url"]: key for key, s in self.sources.items()}
        if len(self.urls) != len(self.sources):
            raise ValueError("Executor requires distinct source URLs within each case")
        self.used = set()
        self.trace = trace

    async def search(self, queries, max_results, *, include_activity=False):
        results, events = [], []
        for query in queries:
            selected = rank(query, self.sources, lambda key: self.sources[key]["text"], lambda key: key)[:max_results]
            for key in selected:
                source = self.sources[key]
                # Smoke fixtures have non-HTTP origins; this address is never fetched.
                url = source["url"] if source["url"].startswith(("https://", "http://")) else f"https://evaluation.invalid/{key}"
                result = SearchResult(title=key, url=url, content="", provider="frozen-corpus",
                                      query=query, matched_queries=[query])
                self.urls[str(result.url)] = key
                results.append(result)
            events.append({"provider": "frozen-corpus", "query": query, "status": "SUCCESS",
                           "candidate_count": len(selected)})
            self.trace.append({"event": "local_search", "query": query, "source_ids": selected})
        return (results, events) if include_activity else results

    async def fetch(self, urls):
        if not set(urls) <= self.urls.keys():
            raise ValueError("URL outside the frozen corpus")
        self.used.update(self.urls[url] for url in urls)
        self.trace.append({"event": "local_fetch", "source_ids": [self.urls[url] for url in urls]})
        return {url: self.sources[self.urls[url]]["text"] for url in urls}

    def embedder(self):
        return LocalChunkStore(self)


class LocalChunkStore:
    def __init__(self, corpus):
        self.corpus = corpus

    async def embed_existing_chunks(self, **kwargs):
        return 0

    async def embed_and_store(self, db, task_id, source_id, text_content, **kwargs):
        records = [DocumentChunk(research_task_id=task_id, source_id=source_id, chunk_index=i,
                                 content=text, token_count=len(text.encode("utf-8")))
                   for i, text in enumerate(chunks(text_content))]
        db.add_all(records)
        return len(records)

    async def search_similar_chunks(self, db, task_id, query, limit=3, **kwargs):
        from app.models.source import ResearchSource
        records = (await db.execute(select(DocumentChunk, ResearchSource.source_tag)
            .join(ResearchSource, ResearchSource.id == DocumentChunk.source_id)
            .where(DocumentChunk.research_task_id == task_id))).all()
        selected = rank(query, records, lambda row: row[0].content,
                        lambda row: (row[1], row[0].chunk_index))[:limit]
        self.corpus.trace.append({"event": "local_retrieve", "query": query,
                                 "chunk_ids": [str(row[0].id) for row in selected]})
        return [(row[0], 0.0) for row in selected]
