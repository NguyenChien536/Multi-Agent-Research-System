import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
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

# ---------------------------------------------------------------------------
# 3. NODE FUNCTIONS (100% Async, Không Placeholder)
# ---------------------------------------------------------------------------

async def supervisor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Supervisor Agent: Đóng vai trò lập kế hoạch và định hướng ban đầu.
    """
    await _record_progress(state, "SUPERVISOR")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    llm = get_fast_llm().with_structured_output(SupervisorPlan)

    prompt = f"""
    Bạn là một Research Supervisor (Chuyên gia hướng dẫn nghiên cứu).
    Đề tài: {state.get('research_question')}
    Độ sâu: {state.get('research_depth')}
    Ngôn ngữ: {state.get('language')}

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

    prompt = f"""
    Bạn là một Nhà văn học thuật chuyên nghiệp. Hãy viết báo cáo nghiên cứu về đề tài: {state.get('research_question')}
    Ngôn ngữ: {state.get('language')}

    Cấu trúc bắt buộc: {plan.get('required_sections', [])}
    Dữ liệu đã trích xuất (chỉ luận điểm có bằng chứng khớp chính xác với đoạn nguồn): {claims}
    Lưu ý từ vòng sửa trước (nếu có): {feedback}

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
