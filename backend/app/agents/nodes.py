import asyncio
import logging
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy import select
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from app.agents.state import ResearchState
from app.core.config import settings
from app.services.agent_run import (
    estimate_cost,
    extract_tokens,
    get_active_model_name,
    record_agent_run,
)

logger = logging.getLogger(__name__)


async def _record_progress(state: ResearchState, step: str, iteration: int | None = None) -> None:
    from app.services.progress import record_agent_progress

    await record_agent_progress(
        state.get("task_id"),
        state.get("attempt_number"),
        step,
        iteration,
    )

# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------
from langchain_core.globals import set_llm_cache
from redis import Redis as _Redis
try:
    from langchain_community.cache import RedisCache  # type: ignore[import]
except ModuleNotFoundError as exc:
    if exc.name != "langchain_community":
        raise
    RedisCache = None  # type: ignore[assignment,misc]

if RedisCache is not None:
    try:
        _redis_client = _Redis.from_url(settings.REDIS_URL)
        set_llm_cache(RedisCache(redis_=_redis_client))
        logger.info("LLM Redis cache enabled")
    except Exception as exc:
        logger.warning("Could not connect to Redis for the LLM cache: %s", exc)
else:
    logger.warning("langchain_community is not installed; LLM Redis cache is disabled")
# 1. TIERED LLM CONFIGURATION (Theo Kiến trúc Tối ưu Hiệu năng)
# ---------------------------------------------------------------------------

# Mô hình nhỏ siêu tốc cho logic, trích xuất (Supervisor, Analyst, Critic)
def build_llm_chain(is_smart: bool = False):
    providers = [p.strip().lower() for p in settings.LLM_PROVIDER_PRIORITY.split(",")]
    models = []
    
    for provider in providers:
        if provider == "gemini" and getattr(settings, "GEMINI_API_KEY", None) and "your_" not in settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_name = "gemini-3.5-flash" if is_smart else "gemini-3.5-flash-lite"
            fallback_name = "gemini-3.5-flash-lite" if is_smart else "gemini-3.5-flash"
            primary_gemini = ChatGoogleGenerativeAI(
                model=model_name, 
                temperature=0.7 if is_smart else 0.2, 
                google_api_key=settings.GEMINI_API_KEY
            )
            fallback_gemini = ChatGoogleGenerativeAI(
                model=fallback_name, 
                temperature=0.7 if is_smart else 0.2, 
                google_api_key=settings.GEMINI_API_KEY
            )
            models.append(primary_gemini.with_fallbacks([fallback_gemini]))
        elif provider == "openai" and getattr(settings, "OPENAI_API_KEY", None) and "your_" not in settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            models.append(ChatOpenAI(
                model="gpt-4o" if is_smart else "gpt-4o-mini", 
                temperature=0.7 if is_smart else 0.2, 
                api_key=settings.OPENAI_API_KEY
            ))
        elif provider == "anthropic" and getattr(settings, "ANTHROPIC_API_KEY", None) and "your_" not in settings.ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            models.append(ChatAnthropic(
                model="claude-3-5-sonnet-20240620" if is_smart else "claude-3-5-haiku-20241022", 
                temperature=0.7 if is_smart else 0.2, 
                api_key=settings.ANTHROPIC_API_KEY
            ))
        elif provider == "groq" and getattr(settings, "GROQ_API_KEY", None) and "your_" not in settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            models.append(ChatGroq(
                model="llama-3.1-8b-instant", 
                temperature=0.7 if is_smart else 0.2, 
                api_key=settings.GROQ_API_KEY
            ))
            
    if not models:
        raise ValueError("Cần cấu hình ít nhất 1 API KEY hợp lệ trong LLM_PROVIDER_PRIORITY")
        
    primary_llm = models[0]
    if len(models) > 1:
        # Fallback chain: Primary -> Fallback 1 -> Fallback 2
        return primary_llm.with_fallbacks(models[1:])
    return primary_llm

def get_fast_llm():
    return build_llm_chain(is_smart=False)

def get_smart_llm():
    return build_llm_chain(is_smart=True)

# ---------------------------------------------------------------------------
# 2. SCHEMAS (Pydantic v2) CHO CÁC AGENT
# ---------------------------------------------------------------------------

class SupervisorPlan(BaseModel):
    research_angle: str = Field(description="Góc nhìn và phương pháp tiếp cận đề tài")
    search_queries: List[str] = Field(description="Danh sách các truy vấn tìm kiếm (tối đa 5)")
    required_sections: List[str] = Field(description="Các mục bắt buộc phải có trong báo cáo")

class CriticVerdict(BaseModel):
    verdict: str = Field(description="Kết luận: 'PASS', 'REVISE', hoặc 'NEED_MORE_DATA'")
    feedback: List[str] = Field(description="Nhận xét chi tiết để Writer sửa (nếu REVISE)")
    missing_areas: List[str] = Field(description="Các mảng thông tin bị thiếu (nếu NEED_MORE_DATA)")

class ExtractedClaim(BaseModel):
    claim: str = Field(description="Luận điểm chính được rút ra")
    evidence_quote: str = Field(description="Trích dẫn nguyên văn làm bằng chứng")

class AnalystExtraction(BaseModel):
    claims: List[ExtractedClaim] = Field(description="Danh sách các luận điểm và bằng chứng")


class MethodologistProtocol(BaseModel):
    research_questions: List[str] = Field(description="Các câu hỏi nghiên cứu cụ thể cần giải quyết")
    hypotheses: List[str] = Field(description="Các giả thuyết nghiên cứu có thể kiểm định (H1, H2,...)")
    variables: Dict[str, List[str]] = Field(description="Các nhóm biến số nghiên cứu (independent, dependent, control)")
    study_design: str = Field(description="Thiết kế nghiên cứu, đối tượng khảo sát/thực nghiệm, cỡ mẫu dự kiến")
    data_collection_procedure: str = Field(description="Quy trình thu thập dữ liệu chi tiết")
    analysis_plan: str = Field(description="Kế hoạch phân tích thống kê và kiểm định giả thuyết")
    ethical_considerations: str = Field(description="Các lưu ý về đạo đức nghiên cứu và bảo mật dữ liệu")
    protocol_markdown: str = Field(description="Bản đề cương nghiên cứu hoàn chỉnh định dạng Markdown")

# ---------------------------------------------------------------------------
# 3. NODE FUNCTIONS (100% Async, Không Placeholder)
# ---------------------------------------------------------------------------

async def supervisor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Supervisor Agent: Đóng vai trò lập kế hoạch và định hướng ban đầu.
    """
    await _record_progress(state, "SUPERVISOR")
    start_ts = time.monotonic()
    # Nếu kế hoạch đã được người dùng phê duyệt trước đó, tái sử dụng trực tiếp mà không cần gọi lại LLM
    if state.get("plan_approved") and state.get("plan"):
        logger.info("Task %s: Reusing approved plan without re-planning.", state.get("task_id"))
        approved_plan = state["plan"]
        search_queries = approved_plan.get("search_queries", [])
        return {
            "current_agent": "supervisor",
            "plan": approved_plan,
            "delta_queries": search_queries,
            "current_queries": search_queries,
        }

    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    llm = get_fast_llm().with_structured_output(SupervisorPlan)

    research_type = state.get("research_type", "REVIEW")
    feedback_section = ""
    if state.get("plan_feedback"):
        feedback_section = f"\n    Lưu ý/Góp ý điều chỉnh từ người dùng: {state.get('plan_feedback')}\n"

    prompt = f"""
    Bạn là một Research Supervisor (Chuyên gia hướng dẫn nghiên cứu).
    Đề tài: {state.get('research_question')}
    Loại nghiên cứu: {research_type}
    Độ sâu: {state.get('research_depth')}
    Ngôn ngữ: {state.get('language')}{feedback_section}

    Hãy lập một kế hoạch nghiên cứu bao gồm góc nhìn, các câu lệnh tìm kiếm Google (search_queries),
    và các cấu trúc mục bắt buộc (required_sections).
    """

    try:
        # Thực thi LLM gọi schema
        plan: SupervisorPlan = await llm.ainvoke([HumanMessage(content=prompt)])
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(plan, prompt_str=prompt, output_str=plan.model_dump_json())
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Supervisor",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"research_question": state.get("research_question"), "depth": state.get("research_depth")},
            output_summary={"queries_count": len(plan.search_queries), "sections_count": len(plan.required_sections)},
            tool_calls=[],
        )

        # Cập nhật State
        return {
            "current_agent": "supervisor",
            "plan": plan.model_dump(),
            "delta_queries": plan.search_queries,
            "current_queries": plan.search_queries
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Supervisor",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def researcher_node(state: ResearchState) -> Dict[str, Any]:
    """
    Researcher Agent: Sử dụng Tavily API để tìm kiếm và cào web song song.
    """
    await _record_progress(state, "RESEARCHER")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    from app.tools.search import execute_parallel_searches
    from app.tools.scraper import fetch_urls_parallel

    queries = state.get("delta_queries", [])
    if not queries:
        return {"current_agent": "researcher"}

    try:
        # 1. Gọi Tavily search (parallel)
        search_results = await execute_parallel_searches(queries, max_results_per_query=3)

        # Bỏ qua các URL đã thu thập trước đó (Seen URL Cache)
        visited = state.get("visited_urls", set())
        new_urls_map = {}
        for res in search_results:
            url_str = str(res.url)
            if url_str not in visited and url_str not in new_urls_map:
                new_urls_map[url_str] = res

        # 2. Cào nội dung (Scraping) song song
        urls_to_scrape = list(new_urls_map.keys())
        scraped_data = await fetch_urls_parallel(urls_to_scrape, max_concurrent=5)

        # 3. Gom kết quả vào state
        new_sources = []
        base_idx = len(state.get("collected_sources", []))

        for url, content in scraped_data.items():
            base_idx += 1
            res = new_urls_map[url]
            source_tag = f"src_{base_idx:02d}"

            new_sources.append({
                "url": url,
                "title": res.title,
                "content": content,
                "source_tag": source_tag
            })

        current_iter = state.get("current_iteration", 0) + 1
        await _record_progress(state, "RESEARCHER", current_iter)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Researcher",
            status="SUCCESS",
            iteration=current_iter,
            attempt_number=state.get("attempt_number", 1),
            model="tavily-search-api",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"queries": queries},
            output_summary={"sources_scraped": len(new_sources), "visited_urls": len(urls_to_scrape)},
            tool_calls=[
                {"tool": "tavily_search", "queries_count": len(queries)},
                {"tool": "scraper", "scraped_count": len(urls_to_scrape)},
            ],
        )

        return {
            "current_agent": "researcher",
            "collected_sources": new_sources,  # Annotated[list, operator.add]
            "visited_urls": set(urls_to_scrape), # Annotated[set, merge_sets]
            "current_iteration": current_iter
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Researcher",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="tavily-search-api",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def curator_node(state: ResearchState) -> Dict[str, Any]:
    """
    Curator Module: Lọc URL trùng lặp, chia nhỏ (Chunking) và nạp vào pgvector.
    Module này chạy code Python 100%, không dùng LLM.
    """
    await _record_progress(state, "CURATOR")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "curator"}

    try:
        task_id = uuid.UUID(task_id_str)
        sources = state.get("collected_sources", [])

        embedder = EmbedderTool()
        chunks_count = 0

        async with AsyncSessionLocal() as db:
            for src in sources:
                if "db_id" in src:
                    continue  # Đã xử lý ở vòng trước

                # Lưu Source vào DB
                db_source = ResearchSource(
                    research_task_id=task_id,
                    source_tag=src["source_tag"],
                    title=src.get("title", ""),
                    url=src.get("url", ""),
                    content_snippet=src.get("content", "")[:500]
                )
                db.add(db_source)
                await db.flush()  # Để lấy db_source.id
                src["db_id"] = str(db_source.id)

                # Chia chunk và nhúng
                count = await embedder.embed_and_store(
                    db=db,
                    task_id=task_id,
                    source_id=db_source.id,
                    text_content=src.get("content", "")
                )
                chunks_count += count

            await db.commit()

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        embedding_tokens = chunks_count * 256
        cost = estimate_cost("gemini-embedding-2", embedding_tokens, 0)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Curator",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="gemini-embedding-2",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=embedding_tokens,
            output_tokens=0,
            estimated_cost=cost,
            input_summary={"sources_count": len(sources)},
            output_summary={"chunks_indexed": chunks_count},
            tool_calls=[{"tool": "embedder", "chunks_indexed": chunks_count}],
        )

        return {
            "current_agent": "curator",
            "indexed_chunks_count": state.get("indexed_chunks_count", 0) + chunks_count
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Curator",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="gemini-embedding-2",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def analyst_node(state: ResearchState) -> Dict[str, Any]:
    """
    Analyst Agent: Dùng Semantic Search RAG để trích xuất Claims + Evidence từ pgvector.
    """
    await _record_progress(state, "ANALYST")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    import uuid
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    llm = get_fast_llm().with_structured_output(AnalystExtraction)
    embedder = EmbedderTool()

    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "analyst"}

    try:
        task_id = uuid.UUID(task_id_str)
        queries = state.get("current_queries", [])
        if not queries:
            queries = [state.get("research_question")]

        all_claims: list[Dict[str, Any]] = []

        # Dùng asyncio.gather để xử lý song song các queries
        async def process_query(query: str) -> tuple[List[Dict], List[Any]]:
            async with AsyncSessionLocal() as db:
                # RAG: Lấy top 3 chunks liên quan nhất cho query
                similar_chunks = await embedder.search_similar_chunks(db, task_id, query, limit=3)

                if not similar_chunks:
                    return [], []

                retrieved_chunks = [chunk for chunk, _distance in similar_chunks]
                chunk_context = []
                for chunk in retrieved_chunks:
                    source = await db.scalar(
                        select(ResearchSource).where(
                            ResearchSource.id == chunk.source_id,
                            ResearchSource.research_task_id == task_id,
                        )
                    )
                    if source is not None:
                        chunk_context.append(
                            f"Source tag: {source.source_tag}\n"
                            f"Chunk ID: {chunk.id}\n"
                            f"Source: {source.title or source.url}\n"
                            f"Content: {chunk.content}"
                        )

                # Ghép nội dung
                context_text = "\n\n".join(chunk_context)

                prompt = f"""
                Dựa vào các tài liệu sau, hãy trích xuất các luận điểm và bằng chứng liên quan đến truy vấn: '{query}'
                Tài liệu:
                {context_text}
                """

                try:
                    extraction = await llm.ainvoke([HumanMessage(content=prompt)])
                    return [c.model_dump() for c in extraction.claims], retrieved_chunks
                except Exception as e:
                    print(f"Lỗi khi trích xuất claims: {e}")
                    return [], []

        # Chạy song song tất cả các queries
        tasks = [process_query(q) for q in queries]
        results = await asyncio.gather(*tasks)
        from app.services.grounding import persist_grounded_claims

        async with AsyncSessionLocal() as db:
            for extracted, retrieved_chunks in results:
                all_claims.extend(
                    await persist_grounded_claims(db, task_id, extracted, retrieved_chunks)
                )
            await db.commit()

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok = max(100, len(queries) * 600)
        out_tok = max(50, len(all_claims) * 50)
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Analyst",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"queries_count": len(queries)},
            output_summary={"verified_claims_count": len(all_claims)},
            tool_calls=[{"tool": "semantic_search", "query_count": len(queries)}],
        )

        return {
            "current_agent": "analyst",
            "claims": all_claims  # Only source-verified claims with persisted IDs.
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Analyst",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def methodologist_node(state: ResearchState) -> Dict[str, Any]:
    """
    Methodologist Agent:
    - Thiết lập Đề cương nghiên cứu khoa học (Study Protocol): giả thuyết, biến số, cỡ mẫu, quy trình thu thập.
    - Lưu đề cương thành file Markdown trong ArtifactStore làm tài liệu trung gian (intermediate artifact).
    - Tạo bản ghi ExportArtifact (export_type='PROTOCOL') trong CSDL gắn với task.
    - Nếu research_type == 'EMPIRICAL_HUMAN' và chưa có user_data_submission:
      trạng thái workflow chuyển thành WAITING_USER_DATA để người dùng tiến hành khảo sát/lab thực tế.
    """
    await _record_progress(state, "METHODOLOGIST")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=True)

    task_id_str = state.get("task_id")
    task_uuid = uuid.UUID(task_id_str) if task_id_str else uuid.uuid4()
    research_type = state.get("research_type", "EMPIRICAL_HUMAN")
    user_data = state.get("user_data_submission")

    # Nếu đã có protocol trong state từ trước, tái sử dụng để tiết kiệm chi phí
    existing_protocol = state.get("protocol")
    if existing_protocol and existing_protocol.get("hypotheses"):
        logger.info("Methodologist: Reusing existing study protocol for task %s", task_id_str)
        status = "WAITING_USER_DATA" if (research_type == "EMPIRICAL_HUMAN" and not user_data) else "RUNNING"
        return {
            "current_agent": "methodologist",
            "protocol": existing_protocol,
            "protocol_artifact_id": state.get("protocol_artifact_id"),
            "status": status,
        }

    claims = state.get("claims", [])
    prompt = f"""
    Bạn là một Nhà phương pháp học khoa học (Methodologist Agent) chuyên nghiệp.
    Hãy xây dựng Đề cương nghiên cứu khoa học (Study Protocol) chi tiết cho đề tài sau:
    Câu hỏi nghiên cứu: {state.get('research_question')}
    Loại nghiên cứu: {research_type}
    Ngôn ngữ: {state.get('language', 'vi')}

    Bối cảnh từ các tài liệu đã tổng hợp:
    {[c.get('claim_text', '') for c in claims[:10]]}

    Yêu cầu:
    1. Xác định các câu hỏi nghiên cứu cụ thể.
    2. Đưa ra ít nhất 2 giả thuyết nghiên cứu có thể kiểm định (H1, H2,...).
    3. Phân loại rõ biến độc lập (independent), biến phụ thuộc (dependent), biến kiểm soát (control).
    4. Thiết kế nghiên cứu và xác định cỡ mẫu tối thiểu hợp lý.
    5. Hướng dẫn quy trình thu thập dữ liệu chi tiết (bảng câu hỏi hoặc thao tác thực nghiệm).
    6. Kế hoạch phân tích dữ liệu và các kiểm định thống kê.
    7. Lưu ý về đạo đức nghiên cứu và bảo mật dữ liệu.
    8. Viết toàn bộ văn bản đề cương hoàn chỉnh dưới dạng Markdown đầy đủ, chuẩn mực.
    """

    try:
        llm = get_smart_llm().with_structured_output(MethodologistProtocol)
        proto_result: MethodologistProtocol = await llm.ainvoke([HumanMessage(content=prompt)])
        protocol_dict = proto_result.model_dump()
        markdown_content = proto_result.protocol_markdown or ""

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(proto_result, prompt_str=prompt, output_str=markdown_content)
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=task_id_str,
            agent_name="Methodologist",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"claims_considered": len(claims)},
            output_summary={
                "hypotheses_count": len(proto_result.hypotheses),
            },
            tool_calls=[{"tool": "generate_protocol"}],
        )

        status = "WAITING_USER_DATA" if (research_type == "EMPIRICAL_HUMAN" and not user_data) else "RUNNING"
        return {
            "current_agent": "methodologist",
            "protocol": protocol_dict,
            "status": status,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=task_id_str,
            agent_name="Methodologist",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def experiment_runner_node(state: ResearchState) -> Dict[str, Any]:
    """
    Experiment Runner Node (Phase 5):
    - Chạy routine tính toán chuẩn tabular_regression_v1 cho bài nghiên cứu dạng EMPIRICAL_COMPUTATIONAL.
    - Chỉ sử dụng dataset_csv do người dùng nạp; không tạo dữ liệu giả cho bài nghiên cứu.
    - Thực hiện kiểm tái lập (repeatability verification) tự động bằng lần chạy thứ hai từ cùng manifest.
    - Sinh các mục sổ nhật ký thí nghiệm ExperimentJournalEntry (append-only) theo chuẩn ADR-005.
    """
    await _record_progress(state, "EXPERIMENT_RUNNER")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = "tabular_regression_v1_engine"

    task_id_str = state.get("task_id")
    dataset_csv = state.get("dataset_csv")

    from app.services.experiment_runner import run_tabular_regression_v1, verify_repeatability

    try:
        if not dataset_csv:
            raise ValueError("A user-provided CSV dataset is required for computational empirical analysis")

        run_result = run_tabular_regression_v1(dataset_csv, seed=42)
        passed, diff = verify_repeatability(dataset_csv, run_result)

        analysis_run = {
            "routine_name": "tabular_regression_v1",
            "status": "COMPLETED",
            "input_checksum": run_result["input_checksum"],
            "manifest": run_result["manifest"],
            "metrics": run_result["metrics"],
            "chart_data": run_result["chart_data"],
            "reproducibility_status": "PASSED" if passed else "FAILED",
            "reproducibility_diff": diff,
            "readme_markdown": run_result["readme_markdown"],
        }

        journal_entries = [
            {
                "sequence": 1,
                "kind": "PLAN_FROZEN",
                "actor": "METHODOLOGIST",
                "payload": {
                    "routine_name": "tabular_regression_v1",
                    "manifest": run_result["manifest"],
                },
            },
            {
                "sequence": 2,
                "kind": "STARTED",
                "actor": "SYSTEM",
                "payload": {
                    "routine_name": "tabular_regression_v1",
                    "input_checksum": run_result["input_checksum"],
                },
            },
            {
                "sequence": 3,
                "kind": "EXECUTION_RESULT",
                "actor": "SYSTEM",
                "payload": {
                    "status": "COMPLETED",
                    "metrics": run_result["metrics"],
                },
            },
            {
                "sequence": 4,
                "kind": "OBSERVATION",
                "actor": "SYSTEM",
                "payload": {
                    "verdict": run_result["verdict"],
                    "comparison": run_result["metrics"]["comparison"],
                },
            },
            {
                "sequence": 5,
                "kind": "REPRODUCTION_CHECK",
                "actor": "SYSTEM",
                "payload": {
                    "status": "PASSED" if passed else "FAILED",
                    "tolerance": diff["tolerance"],
                    "diff": diff,
                },
            },
            {
                "sequence": 6,
                "kind": "INTERPRETATION",
                "actor": "DATA_ANALYST",
                "payload": {
                    "summary": f"Routine tabular_regression_v1 hoàn thành với kết luận {run_result['verdict']}. Ridge MAE: {run_result['metrics']['model']['mae']} so với Baseline MAE: {run_result['metrics']['baseline']['mae']}. Phép kiểm tái lập: {'ĐẠT (PASSED)' if passed else 'KHÔNG ĐẠT (FAILED)'}. Kết quả mang tính chất dự đoán và thăm dò, không suy luận quan hệ nhân quả.",
                },
            },
        ]

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)

        await record_agent_run(
            task_id=task_id_str,
            agent_name="ExperimentRunner",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"rows": run_result["manifest"]["dataset_rows"]},
            output_summary={"verdict": run_result["verdict"], "repeatability": "PASSED" if passed else "FAILED"},
            tool_calls=[{"tool": "tabular_regression_v1"}],
        )

        return {
            "current_agent": "experiment_runner",
            "dataset_csv": dataset_csv,
            "analysis_run": analysis_run,
            "experiment_journal": journal_entries,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=task_id_str,
            agent_name="ExperimentRunner",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        # A failed execution is a technical failure, not a negative scientific
        # result. Preserve a failed AnalysisRun and append-only journal entries
        # even though the graph cannot continue to Writer.
        if task_id_str:
            try:
                from app.core.database import AsyncSessionLocal
                from app.models.experiment import AnalysisRun, ExperimentJournalEntry

                checksum = (
                    hashlib.sha256(dataset_csv.strip().encode("utf-8")).hexdigest()
                    if dataset_csv
                    else None
                )
                dataset_artifact_id = state.get("dataset_artifact_id")
                try:
                    parsed_dataset_artifact_id = (
                        uuid.UUID(str(dataset_artifact_id)) if dataset_artifact_id else None
                    )
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid dataset artifact ID for task %s", task_id_str)
                    parsed_dataset_artifact_id = None
                safe_error = f"{type(exc).__name__}: {str(exc)[:500]}"
                async with AsyncSessionLocal() as session:
                    failed_run = AnalysisRun(
                        research_task_id=uuid.UUID(str(task_id_str)),
                        routine_name="tabular_regression_v1",
                        status="FAILED",
                        dataset_artifact_id=parsed_dataset_artifact_id,
                        input_checksum=checksum,
                        manifest={
                            "manifest_version": "1.0",
                            "routine_name": "tabular_regression_v1",
                            "input_checksum": checksum,
                            "parameters": {"seed": 42},
                        },
                        reproducibility_status="NOT_RUN",
                        error_message=safe_error,
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(failed_run)
                    await session.flush()
                    session.add_all([
                        ExperimentJournalEntry(
                            research_task_id=failed_run.research_task_id,
                            analysis_run_id=failed_run.id,
                            sequence=1,
                            kind="STARTED",
                            actor="SYSTEM",
                            payload={"routine_name": "tabular_regression_v1", "input_checksum": checksum},
                            artifact_ids=(
                                [str(parsed_dataset_artifact_id)] if parsed_dataset_artifact_id else []
                            ),
                        ),
                        ExperimentJournalEntry(
                            research_task_id=failed_run.research_task_id,
                            analysis_run_id=failed_run.id,
                            sequence=2,
                            kind="EXECUTION_RESULT",
                            actor="SYSTEM",
                            payload={"status": "TECHNICAL_FAILURE", "error": safe_error},
                            artifact_ids=(
                                [str(parsed_dataset_artifact_id)] if parsed_dataset_artifact_id else []
                            ),
                        ),
                    ])
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist technical experiment failure for task %s", task_id_str)
        raise

async def writer_node(state: ResearchState) -> Dict[str, Any]:
    """
    Writer Agent: Viết bản nháp dựa trên Claims & Evidences. (Dùng mô hình xịn)
    """
    await _record_progress(state, "WRITER")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=True)
    llm = get_smart_llm()
    plan = state.get("plan", {})
    claims = [
        claim for claim in state.get("claims", [])
        if claim.get("claim_id") and claim.get("evidence_id")
    ]
    feedback = state.get("critic_feedback", [])

    research_type = state.get("research_type", "REVIEW")
    protocol = state.get("protocol") or {}
    user_data = state.get("user_data_submission")
    analysis_run = state.get("analysis_run")

    empirical_section = ""
    if research_type == "EMPIRICAL_HUMAN" and user_data:
        empirical_section = f"""
    LƯU Ý NGHIÊN CỨU THỰC NGHIỆM (EMPIRICAL_HUMAN):
    Đề cương phương pháp:
    - Giả thuyết: {protocol.get('hypotheses', [])}
    - Biến số: {protocol.get('variables', {})}
    - Thiết kế nghiên cứu: {protocol.get('study_design', '')}

    Dữ liệu thực tế do người dùng cung cấp (USER-SUPPLIED FIELDWORK DATA):
    - Cỡ mẫu: {user_data.get('sample_size')}
    - Quy trình thu thập: {user_data.get('method_notes')}
    - Tóm tắt kết quả/số liệu: {user_data.get('results_summary')}
    - Xuất xứ dữ liệu (Provenance): {user_data.get('data_provenance', 'Khảo sát/thực nghiệm do người nghiên cứu thực hiện')}

    Yêu cầu đặc biệt:
    1. Bắt buộc có các phần: Title, Abstract, Introduction, Research Questions & Hypotheses, Methods, Results, Discussion, Limitations, Conclusion, References.
    2. Trong phần Results, BẮT BUỘC ghi rõ provenance: kết quả nào dựa trên dữ liệu người dùng nạp vào và kết quả nào từ tổng quan phân tích.
    """
    elif research_type == "EMPIRICAL_COMPUTATIONAL" and analysis_run:
        m = analysis_run.get("metrics", {})
        base_m = m.get("baseline", {})
        model_m = m.get("model", {})
        comp = m.get("comparison", {})
        verdict = comp.get("verdict", "INCONCLUSIVE")
        repro_status = analysis_run.get("reproducibility_status", "NOT_RUN")

        empirical_section = f"""
    KẾT QUẢ THỰC NGHIỆM TÍNH TOÁN (COMPUTATIONAL EXPERIMENT RESULTS):
    Routine thực thi: {analysis_run.get('routine_name', 'tabular_regression_v1')}
    Tập dữ liệu: {analysis_run.get('manifest', {}).get('valid_rows')} mẫu hợp lệ, split 80/20, seed 42.
    Biến mục tiêu: {analysis_run.get('manifest', {}).get('target_column')}
    Biến đặc trưng: {analysis_run.get('manifest', {}).get('feature_columns')}
    Số liệu đo lường đối chứng:
    - Mean Baseline: MAE = {base_m.get('mae')}, RMSE = {base_m.get('rmse')}, R² = {base_m.get('r2')}
    - Ridge Regression (alpha=1.0): MAE = {model_m.get('mae')}, RMSE = {model_m.get('rmse')}, R² = {model_m.get('r2')}
    - Chênh lệch sai số (Delta MAE): {comp.get('delta_mae')}
    - Kết luận khoa học: {verdict} ({'Ridge cải thiện sai số so với baseline' if verdict == 'IMPROVEMENT' else 'Ridge không vượt trội hơn baseline (kết quả âm hợp lệ)'})
    - Phép kiểm tái lập độc lập (Repeatability Check): {repro_status} (dung sai tolerance <= 1e-8)

    Yêu cầu cấu trúc bắt buộc:
    1. Bắt buộc có các phần: Title, Abstract, Introduction, Research Questions, Methods, Results, Discussion, Limitations, Conclusion, References.
    2. Trong Methods & Results: BẮT BUỘC trình bày cả hai bộ số liệu (Baseline VÀ Ridge) một cách minh bạch, tuyệt đối không chọn lọc chỉ báo cáo mô hình tốt hơn.
    3. Trình bày trung thực kết luận {verdict} và kiểm tra tính tái lập {repro_status}.
    4. Giới hạn khoa học: Kết quả mang tính chất mô tả và dự đoán (predictive/exploratory), tuyệt đối không suy diễn quan hệ nhân quả (non-causal).
    """

    prompt = f"""
    Bạn là một Nhà văn học thuật chuyên nghiệp. Hãy viết báo cáo nghiên cứu về đề tài: {state.get('research_question')}
    Loại nghiên cứu: {research_type}
    Ngôn ngữ: {state.get('language')}

    Cấu trúc bắt buộc: {plan.get('required_sections', [])}
    Dữ liệu đã trích xuất (chỉ luận điểm có bằng chứng khớp chính xác với đoạn nguồn): {claims}
    Lưu ý từ vòng sửa trước (nếu có): {feedback}
    {empirical_section}

    Yêu cầu: Viết theo định dạng Markdown. Khi sử dụng một luận điểm, hãy chèn marker chính xác [[@claim:CLAIM_ID]] với CLAIM_ID lấy từ dữ liệu trên. Không tự tạo nguồn, số citation hoặc URL. Nếu không có luận điểm phù hợp, hãy nêu rõ chưa đủ bằng chứng.
    """

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, list):
            draft_markdown = "".join(
                item if isinstance(item, str) else item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        else:
            draft_markdown = str(content)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(response, prompt_str=prompt, output_str=draft_markdown)
        cost = estimate_cost(model_name, in_tok, out_tok)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Writer",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"claims_count": len(claims)},
            output_summary={"draft_words": len(draft_markdown.split())},
            tool_calls=[],
        )

        return {
            "current_agent": "writer",
            "draft_report_markdown": draft_markdown
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Writer",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def critic_node(state: ResearchState) -> Dict[str, Any]:
    """
    Critic Agent: Đóng vai 'Devil's Advocate' kiểm chứng logic và fact. Trả về JSON ngắn.
    """
    await _record_progress(state, "CRITIC")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    llm = get_fast_llm().with_structured_output(CriticVerdict)
    draft = state.get("draft_report_markdown", "")

    prompt = f"""
    Bạn là một Người phản biện độc lập khắt khe.
    Nhiệm vụ: Đọc bản nháp sau và đánh giá xem nó có đủ dữ liệu, logic, và độ chi tiết không.
    Bản nháp: {draft[:3000]}...
    """

    try:
        verdict: CriticVerdict = await llm.ainvoke([HumanMessage(content=prompt)])
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        in_tok, out_tok = extract_tokens(verdict, prompt_str=prompt, output_str=verdict.model_dump_json())
        cost = estimate_cost(model_name, in_tok, out_tok)

        micro_count = state.get("current_micro_revision", 0) + 1 if verdict.verdict == "REVISE" else state.get("current_micro_revision", 0)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Critic",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost=cost,
            input_summary={"draft_preview_length": len(draft[:3000])},
            output_summary={"verdict": verdict.verdict, "feedback_count": len(verdict.feedback), "missing_areas_count": len(verdict.missing_areas)},
            tool_calls=[],
        )

        return {
            "current_agent": "critic",
            "critic_verdict": verdict.verdict,
            "critic_feedback": verdict.feedback,
            "delta_queries": verdict.missing_areas,
            "current_micro_revision": micro_count
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Critic",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

async def post_processor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Post Processor: Module Regex code để định dạng Markdown cuối cùng và đánh số trích dẫn.
    """
    await _record_progress(state, "POST_PROCESSOR")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    draft = state.get("draft_report_markdown", "")

    import re

    try:
        claims_by_id = {
            str(item.get("claim_id")): item
            for item in state.get("claims", [])
            if item.get("claim_id") and item.get("evidence_id")
        }
        marker_pattern = re.compile(r"\[\[@claim:([0-9a-fA-F-]{36})\]\]")
        used_ids: list[str] = []
        for match in marker_pattern.finditer(draft):
            claim_id = match.group(1)
            if claim_id in claims_by_id and claim_id not in used_ids:
                used_ids.append(claim_id)

        citation_numbers = {claim_id: index for index, claim_id in enumerate(used_ids, start=1)}

        def replace_marker(match: re.Match[str]) -> str:
            number = citation_numbers.get(match.group(1))
            return f"@@VALID_CITATION_{number}@@" if number is not None else ""

        final_md = marker_pattern.sub(replace_marker, draft)
        # Remove all model-authored numbered citations, then restore only markers
        # that resolved to validated claim/evidence records.
        final_md = re.sub(r"\[\d+\]", "", final_md)
        for claim_id, number in citation_numbers.items():
            final_md = final_md.replace(f"@@VALID_CITATION_{number}@@", f"[{number}]")
        final_md = re.sub(r"\[\[@claim:[^\]]+\]\]", "", final_md)
        # Discard a model-authored bibliography and construct it from validated sources.
        final_md = re.sub(
            r"(?ims)^#{1,3}\s*(references|bibliography|works cited)\s*$.*\Z",
            "",
            final_md,
        ).rstrip()
        citation_records = [claims_by_id[claim_id] for claim_id in used_ids]
        if citation_records:
            references = ["", "## References", ""]
            for number, item in enumerate(citation_records, start=1):
                label = item.get("source_title") or item.get("source_url") or item["source_tag"]
                url = item.get("source_url")
                references.append(f"[{number}] {label}" + (f". {url}" if url else "."))
            final_md += "\n".join(references)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="PostProcessor",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="deterministic-regex-processor",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            input_summary={"used_claims_count": len(used_ids)},
            output_summary={"citations_count": len(citation_records), "report_words": len(final_md.split())},
            tool_calls=[],
        )

        return {
            "current_agent": "post_processor",
            "final_report_markdown": final_md,
            "citations": citation_records,
            "status": "COMPLETED"
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="PostProcessor",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model="deterministic-regex-processor",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise
