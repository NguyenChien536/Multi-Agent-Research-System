import logging
from typing import List, Dict, Any, Tuple
import uuid
import asyncio

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select, text, func, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.models.source import DocumentChunk, ResearchSource
from app.services.agent_run import estimate_cost
from app.services.provider_budget import (
    ProviderBudgetExceeded,
    ResearchTaskStopped,
    assert_task_active,
    estimate_tokens,
    reserve_provider_call,
    settle_provider_call,
)
from app.services.evidence_selection import (
    MAX_STORED_CHUNKS, MAX_VECTOR_CHUNKS, spread_indexes, query_terms, fuse_diverse_chunks,
)

logger = logging.getLogger(__name__)


def _source_balanced_statement(task_id, score, pool_size, per_source, *, descending=False, extra_scope=()):
    """Limit each source before the global pool, so one long PDF cannot crowd it out."""
    order = score.desc() if descending else score.asc()
    candidates = select(
        DocumentChunk.id.label("chunk_id"), score.label("retrieval_score"),
        func.row_number().over(partition_by=DocumentChunk.source_id,
                               order_by=(order, DocumentChunk.chunk_index, DocumentChunk.id)).label("source_position"),
    ).join(ResearchSource, ResearchSource.id == DocumentChunk.source_id).where(
        DocumentChunk.research_task_id == task_id, ResearchSource.research_task_id == task_id,
        ResearchSource.ingestion_status == "READY", *extra_scope,
    ).subquery()
    result_order = candidates.c.retrieval_score.desc() if descending else candidates.c.retrieval_score.asc()
    return select(DocumentChunk, candidates.c.retrieval_score).join(
        candidates, candidates.c.chunk_id == DocumentChunk.id,
    ).where(candidates.c.source_position <= per_source).order_by(
        result_order, DocumentChunk.source_id, DocumentChunk.chunk_index, DocumentChunk.id,
    ).limit(pool_size)


class EmbedderTool:
    """Công cụ băm nhỏ văn bản (Chunking) và Vector Embedding."""

    def __new__(cls, *args, **kwargs):
        from app.core.runtime import current_runtime
        if runtime := current_runtime():
            return runtime.embedder()
        return super().__new__(cls)

    def __init__(self, api_key: str | None = None):
        self.dimension = settings.EMBEDDING_DIMENSION
        self.embeddings = None
        providers = [p.strip().lower() for p in settings.EMBEDDING_PROVIDER_PRIORITY.split(",")]
        
        for provider in providers:
            if provider == "gemini" and getattr(settings, "GEMINI_API_KEY", None) and "your_" not in settings.GEMINI_API_KEY:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                self.model_name = "models/gemini-embedding-2"
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=settings.GEMINI_API_KEY,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                self.dimension = 3072
                break
            elif provider == "openai" and getattr(settings, "OPENAI_API_KEY", None) and "your_" not in settings.OPENAI_API_KEY:
                self.model_name = settings.EMBEDDING_MODEL or "text-embedding-3-small"
                self.embeddings = OpenAIEmbeddings(
                    api_key=settings.OPENAI_API_KEY,
                    model=self.model_name,
                    dimensions=self.dimension
                )
                break
                
        if not self.embeddings:
            logger.warning("Không tìm thấy API KEY hợp lệ trong EMBEDDING_PROVIDER_PRIORITY. Embedder sẽ không hoạt động.")

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk_text(self, text_content: str, metadata: dict = None) -> List[Document]:
        """Băm nhỏ văn bản thành các chunks."""
        metadata = metadata or {}
        return self.text_splitter.create_documents([text_content], metadatas=[metadata])

    async def embed_and_store(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        source_id: uuid.UUID,
        text_content: str,
        budget_context: dict[str, Any] | None = None,
    ) -> int:
        """Cắt chuỗi, tạo embedding và lưu vào pgvector thông qua SQLAlchemy."""
        # Keep bounded text across the document. Only eight representative
        # chunks need vectors; later Methods/Results remain lexically searchable.
        docs = self.chunk_text(text_content)
        if not docs:
            return 0

        indexes = spread_indexes(len(docs), MAX_STORED_CHUNKS)
        stored_texts = [docs[i].page_content for i in indexes]
        vector_indexes = spread_indexes(len(stored_texts), MAX_VECTOR_CHUNKS)
        texts = [stored_texts[i] for i in vector_indexes]
        vectors = [None] * len(texts)

        if self.embeddings and budget_context:
            # 2. Embedding (Gộp batch & Retry)
            from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
            import asyncio
            
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=2, min=3, max=15),
                retry=retry_if_not_exception_type((ProviderBudgetExceeded, ResearchTaskStopped)),
            )
            async def _embed_with_retry(texts_batch):
                reservation_id = None
                input_tokens = sum(estimate_tokens(item) for item in texts_batch)
                reservation_id = await reserve_provider_call(
                    task_id=budget_context["task_id"],
                    attempt_number=budget_context["attempt_number"],
                    kind="embedding",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    allow_pre_run=bool(budget_context.get("allow_pre_run")),
                )
                try:
                    await assert_task_active(
                        budget_context["task_id"], budget_context["attempt_number"],
                        allow_pre_run=bool(budget_context.get("allow_pre_run")),
                    )
                    result = await self.embeddings.aembed_documents(texts_batch)
                    if len(result) != len(texts_batch):
                        raise RuntimeError("Embedding provider returned a different number of vectors than requested")
                    if reservation_id:
                        await settle_provider_call(
                            task_id=budget_context["task_id"], reservation_id=reservation_id,
                            input_tokens=input_tokens, output_tokens=0,
                            cost_usd=estimate_cost(self.model_name, input_tokens, 0), succeeded=True,
                        )
                        await assert_task_active(
                            budget_context["task_id"], budget_context["attempt_number"],
                            allow_pre_run=bool(budget_context.get("allow_pre_run")),
                        )
                    return result
                except Exception:
                    if reservation_id:
                        await settle_provider_call(
                            task_id=budget_context["task_id"], reservation_id=reservation_id,
                            input_tokens=0, output_tokens=0, cost_usd=0, succeeded=False,
                        )
                    raise
                
            # Nếu là Google Gemini (Free Tier), áp dụng Rate Limit (batch_size=20, sleep=2s)
            # Nếu là OpenAI (Trả phí), bơm thẳng 1 lần để tối ưu tốc độ 100%
            if "gemini" in self.model_name.lower() or "google" in str(type(self.embeddings)).lower():
                batch_size = 20
                sleep_time = 2
            else:
                batch_size = len(texts) if texts else 1
                sleep_time = 0
                
            try:
                computed_vectors = []
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i+batch_size]
                    batch_vectors = await _embed_with_retry(batch_texts)
                    computed_vectors.extend(batch_vectors)
                    if sleep_time > 0 and i + batch_size < len(texts):
                        await asyncio.sleep(sleep_time)
                vectors = computed_vectors
            except Exception as e:
                if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)):
                    raise
                logger.warning(f"Embedding API temporarily unavailable ({e}), proceeding with non-vector chunks")
                vectors = [None] * len(texts)
        elif not self.embeddings:
            logger.warning("No embedding provider is configured; storing text chunks without vectors")
        else:
            logger.warning(
                "Embedding provider call skipped because no active task budget is attached; storing text chunks only"
            )

        # 3. Lưu vào Database
        chunks_to_insert = []
        vector_by_index = dict(zip(vector_indexes, vectors))
        for i, content in enumerate(stored_texts):
            chunk = DocumentChunk(
                research_task_id=task_id,
                source_id=source_id,
                chunk_index=indexes[i],
                content=content,
                embedding=vector_by_index.get(i),
                token_count=len(content) // 4
            )
            chunks_to_insert.append(chunk)

        db.add_all(chunks_to_insert)
        return len(chunks_to_insert)

    async def embed_existing_chunks(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        source_id: uuid.UUID,
        budget_context: dict[str, Any],
    ) -> int:
        """Embed text-only chunks created during upload, inside the active run budget."""
        if not self.embeddings:
            return 0
        source = await db.scalar(select(ResearchSource).where(
            ResearchSource.id == source_id, ResearchSource.research_task_id == task_id))
        if source is None:
            return 0
        result = await db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.research_task_id == task_id,
                DocumentChunk.source_id == source_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        all_chunks = list(result.scalars().all())
        if source.upload_artifact_id is None:
            # Web corpora intentionally keep extra text for lexical retrieval.
            # A macro loop must not silently embed every previously text-only chunk.
            candidates = [all_chunks[i] for i in spread_indexes(len(all_chunks), MAX_VECTOR_CHUNKS)]
        else:
            candidates = all_chunks  # Preserve the existing uploaded-PDF ingestion path.
        chunks = [chunk for chunk in candidates if chunk.embedding is None]
        if not chunks:
            return 0

        batch_size = 20 if "gemini" in self.model_name.lower() else len(chunks)
        embedded_count = 0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            texts = [chunk.content for chunk in batch]
            input_tokens = sum(estimate_tokens(item) for item in texts)
            last_error: Exception | None = None
            for attempt in range(3):
                reservation_id = await reserve_provider_call(
                    task_id=budget_context["task_id"],
                    attempt_number=budget_context["attempt_number"],
                    kind="embedding",
                    model=self.model_name,
                    input_tokens=input_tokens,
                )
                try:
                    await assert_task_active(
                        budget_context["task_id"], budget_context["attempt_number"],
                        allow_pre_run=bool(budget_context.get("allow_pre_run")),
                    )
                    vectors = await self.embeddings.aembed_documents(texts)
                    if len(vectors) != len(batch):
                        raise RuntimeError("Embedding provider returned a different number of vectors than requested")
                    await settle_provider_call(
                        task_id=budget_context["task_id"], reservation_id=reservation_id,
                        input_tokens=input_tokens, output_tokens=0,
                        cost_usd=estimate_cost(self.model_name, input_tokens, 0), succeeded=True,
                    )
                    await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])
                    for chunk, vector in zip(batch, vectors):
                        chunk.embedding = vector
                    embedded_count += len(batch)
                    last_error = None
                    break
                except (ProviderBudgetExceeded, ResearchTaskStopped):
                    raise
                except Exception as exc:
                    last_error = exc
                    await settle_provider_call(
                        task_id=budget_context["task_id"], reservation_id=reservation_id,
                        input_tokens=0, output_tokens=0, cost_usd=0, succeeded=False,
                    )
                    if attempt < 2:
                        await asyncio.sleep(min(3 * (2 ** attempt), 15))
            if last_error:
                logger.warning("Could not embed uploaded source chunks after retries: %s", last_error)
                break
        return embedded_count

    async def search_similar_chunks(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        query: str,
        limit: int = 5,
        budget_context: dict[str, Any] | None = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Tìm kiếm ngữ nghĩa (Semantic Search) trong scope của 1 Research Task.
        Hybrid vector/lexical rank with source diversity; score is a fused rank,
        not a cosine distance or evidence-confidence estimate.
        """
        if limit <= 0:
            return []
        pool_size = min(max(limit * 6, 18), 90)
        per_source = max(3, min(limit, 8))
        source_scope = (
            ResearchSource.research_task_id == task_id,
            ResearchSource.ingestion_status == "READY",
        )
        vector_rows = []
        vector_scope = [DocumentChunk.embedding.is_not(None)]
        if expected_dimension := getattr(self, "dimension", None):
            # Do not bill query embeddings against an incompatible historical corpus.
            vector_scope.append(func.vector_dims(DocumentChunk.embedding) == expected_dimension)
        has_vectors = await db.scalar(
            select(DocumentChunk.id)
            .join(ResearchSource, ResearchSource.id == DocumentChunk.source_id)
            .where(
                DocumentChunk.research_task_id == task_id,
                *vector_scope,
                *source_scope,
            )
            .limit(1)
        )
        if has_vectors and self.embeddings and budget_context:
            try:
                reservation_id = None
                input_tokens = estimate_tokens(query)
                reservation_id = await reserve_provider_call(
                    task_id=budget_context["task_id"],
                    attempt_number=budget_context["attempt_number"],
                    kind="embedding",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    allow_pre_run=bool(budget_context.get("allow_pre_run")),
                )
                try:
                    await assert_task_active(
                        budget_context["task_id"], budget_context["attempt_number"],
                        allow_pre_run=bool(budget_context.get("allow_pre_run")),
                    )
                    query_vector = await self.embeddings.aembed_query(query)
                    if reservation_id:
                        await settle_provider_call(
                            task_id=budget_context["task_id"], reservation_id=reservation_id,
                            input_tokens=input_tokens, output_tokens=0,
                            cost_usd=estimate_cost(self.model_name, input_tokens, 0), succeeded=True,
                        )
                        await assert_task_active(
                            budget_context["task_id"], budget_context["attempt_number"],
                            allow_pre_run=bool(budget_context.get("allow_pre_run")),
                        )
                except Exception:
                    if reservation_id:
                        await settle_provider_call(
                            task_id=budget_context["task_id"], reservation_id=reservation_id,
                            input_tokens=0, output_tokens=0, cost_usd=0, succeeded=False,
                        )
                    raise
                stmt = _source_balanced_statement(task_id, DocumentChunk.embedding.cosine_distance(query_vector),
                                                   pool_size, per_source, extra_scope=vector_scope)
                # A failed distance query must not poison the enclosing session
                # before the lexical path (for example, incompatible dimensions).
                async with db.begin_nested():
                    result = await db.execute(stmt)
                    vector_rows = result.all()
            except Exception as e:
                if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)):
                    raise
                logger.warning("Vector retrieval unavailable; using lexical evidence ranking: %s", type(e).__name__)

        lexical_rows = []
        terms = query_terms(query)
        if terms:
            config = literal_column("'simple'")
            document = func.to_tsvector(config, DocumentChunk.content)
            tsquery = func.websearch_to_tsquery(config, " OR ".join(f'"{term}"' for term in terms))
            rank = func.ts_rank_cd(document, tsquery)
            lexical_stmt = _source_balanced_statement(task_id, rank, pool_size, per_source, descending=True,
                                                       extra_scope=[document.op("@@")(tsquery)])
            lexical_rows = (await db.execute(lexical_stmt)).all()
        return fuse_diverse_chunks(vector_rows, lexical_rows, limit)
