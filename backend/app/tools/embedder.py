import logging
from typing import List, Dict, Any, Tuple
import uuid
import asyncio

from langchain_openai import AsyncOpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.models.source import DocumentChunk, ResearchSource

logger = logging.getLogger(__name__)

class EmbedderTool:
    """Công cụ băm nhỏ văn bản (Chunking) và Vector Embedding."""

    def __init__(self, api_key: str | None = None):
        self.dimension = settings.EMBEDDING_DIMENSION  # Default: 1536
        self.embeddings = None

        # 1. Ưu tiên OpenAI Embeddings
        if getattr(settings, "OPENAI_API_KEY", None) and "your_" not in settings.OPENAI_API_KEY:
            self.model_name = settings.EMBEDDING_MODEL or "text-embedding-3-small"
            self.embeddings = AsyncOpenAIEmbeddings(
                api_key=settings.OPENAI_API_KEY,
                model=self.model_name,
                dimensions=self.dimension
            )
        # 2. Dự phòng Gemini Embeddings
        elif getattr(settings, "GEMINI_API_KEY", None) and "your_" not in settings.GEMINI_API_KEY:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            self.model_name = "models/gemini-embedding-2"
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=self.model_name,
                google_api_key=settings.GEMINI_API_KEY,
                task_type="RETRIEVAL_DOCUMENT"
            )
            self.dimension = 768
        else:
            logger.warning("Không tìm thấy API KEY hợp lệ. Embedder sẽ không hoạt động.")

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
        text_content: str
    ) -> int:
        """Cắt chuỗi, tạo embedding và lưu vào pgvector thông qua SQLAlchemy."""
        if not self.embeddings:
            raise ValueError("Chưa cấu hình OPENAI_API_KEY cho EmbedderTool.")

        # 1. Chunking
        docs = self.chunk_text(text_content)
        if not docs:
            return 0

        texts = [doc.page_content for doc in docs]

        # 2. Embedding (Gộp batch để gọi API 1 lần)
        try:
            vectors = await self.embeddings.aembed_documents(texts)
        except Exception as e:
            logger.error(f"Lỗi khi gọi OpenAI Embedding API: {str(e)}")
            raise

        # 3. Lưu vào Database
        chunks_to_insert = []
        for i, (content, vector) in enumerate(zip(texts, vectors)):
            chunk = DocumentChunk(
                research_task_id=task_id,
                source_id=source_id,
                chunk_index=i,
                content=content,
                embedding=vector,
                token_count=len(content) // 4  # Ước lượng token cơ bản
            )
            chunks_to_insert.append(chunk)

        db.add_all(chunks_to_insert)
        # Commit sẽ được thực hiện bởi caller (Supervisor hoặc Agent)

        return len(chunks_to_insert)

    async def search_similar_chunks(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        query: str,
        limit: int = 5
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Tìm kiếm ngữ nghĩa (Semantic Search) trong scope của 1 Research Task.
        Trả về danh sách (DocumentChunk, khoảng cách cosine).
        Khoảng cách càng nhỏ càng giống nhau.
        """
        if not self.embeddings:
            raise ValueError("Chưa cấu hình OpenAI API Key cho EmbedderTool.")

        # 1. Tạo embedding cho câu truy vấn
        query_vector = await self.embeddings.aembed_query(query)

        # 2. Tìm kiếm vector bằng pgvector cosine distance (<=>)
        stmt = (
            select(DocumentChunk, DocumentChunk.embedding.cosine_distance(query_vector).label("distance"))
            .where(DocumentChunk.research_task_id == task_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(limit)
        )

        result = await db.execute(stmt)
        # result.all() trả về list of tuples: (DocumentChunk, distance)
        return result.all()
