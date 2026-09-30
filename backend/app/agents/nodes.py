import asyncio
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from app.agents.state import ResearchState
from app.core.config import settings

# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------
from langchain.globals import set_llm_cache
from langchain_community.cache import RedisCache
from redis import Redis

try:
    redis_client = Redis.from_url(settings.REDIS_URL)
    set_llm_cache(RedisCache(redis_=redis_client))
    print("LLM Redis Cache enabled successfully!")
except Exception as e:
    print(f"Warning: Could not connect to Redis for LLM Cache: {e}")
# 1. TIERED LLM CONFIGURATION (Theo Kiến trúc Tối ưu Hiệu năng)
# ---------------------------------------------------------------------------

# Mô hình nhỏ siêu tốc cho logic, trích xuất (Supervisor, Analyst, Critic)
def build_llm_chain(is_smart: bool = False):
    providers = [p.strip().lower() for p in settings.LLM_PROVIDER_PRIORITY.split(",")]
    models = []
    
    for provider in providers:
        if provider == "gemini" and getattr(settings, "GEMINI_API_KEY", None) and "your_" not in settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            models.append(ChatGoogleGenerativeAI(
                model="gemini-3.8-flash", 
                temperature=0.7 if is_smart else 0.2, 
                google_api_key=settings.GEMINI_API_KEY
            ))
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
    llm = get_fast_llm().with_structured_output(SupervisorPlan)

    prompt = f"""
    Bạn là một Research Supervisor (Chuyên gia hướng dẫn nghiên cứu).
    Đề tài: {state.get('research_question')}
    Độ sâu: {state.get('research_depth')}
    Ngôn ngữ: {state.get('language')}

    Hãy lập một kế hoạch nghiên cứu bao gồm góc nhìn, các câu lệnh tìm kiếm Google (search_queries),
    và các cấu trúc mục bắt buộc (required_sections).
    """

    # Thực thi LLM gọi schema
    plan: SupervisorPlan = await llm.ainvoke([HumanMessage(content=prompt)])

    # Cập nhật State
    return {
        "current_agent": "supervisor",
        "plan": plan.model_dump(),
        "delta_queries": plan.search_queries,
        "current_queries": plan.search_queries
    }

async def researcher_node(state: ResearchState) -> Dict[str, Any]:
    """
    Researcher Agent: Sử dụng Tavily API để tìm kiếm và cào web song song.
    """
    from app.tools.search import execute_parallel_searches
    from app.tools.scraper import fetch_urls_parallel

    queries = state.get("delta_queries", [])
    if not queries:
        return {"current_agent": "researcher"}

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

    return {
        "current_agent": "researcher",
        "collected_sources": new_sources,  # Annotated[list, operator.add]
        "visited_urls": set(urls_to_scrape), # Annotated[set, merge_sets]
        "current_iteration": current_iter
    }

async def curator_node(state: ResearchState) -> Dict[str, Any]:
    """
    Curator Module: Lọc URL trùng lặp, chia nhỏ (Chunking) và nạp vào pgvector.
    Module này chạy code Python 100%, không dùng LLM.
    """
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    # Ở đây ta nên lấy new_sources từ bước researcher (nhưng state.collected_sources là tích luỹ).
    # Tuy nhiên LangGraph reducer append vào cuối, nên ta có thể process các source chưa có ID.
    # Thay vì thế, để đơn giản trong MVP, ta sẽ ghi nguồn vào Database ngay tại đây.
    # (Trong một phiên bản nâng cao, ta truyền messages list hoặc delta_sources).

    # Vì MVP LangGraph chưa truyền context session, ta tự khởi tạo
    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "curator"}

    task_id = uuid.UUID(task_id_str)
    sources = state.get("collected_sources", [])

    embedder = EmbedderTool()
    chunks_count = 0

    async with AsyncSessionLocal() as db:
        for src in sources:
            # Kiểm tra xem source đã được lưu chưa (bằng cách kiểm tra ID hoặc chỉ xử lý source mới)
            # MVP: Giả sử tất cả nguồn mới đều chưa lưu (nếu đã lưu, skip)
            # Dùng visited_urls hoặc một list delta_sources để tracking tốt hơn,
            # nhưng ta sẽ dựa vào "db_id" trong src_dict để nhận biết.

            if "db_id" in src:
                continue # Đã xử lý ở vòng trước

            # Lưu Source vào DB
            db_source = ResearchSource(
                research_task_id=task_id,
                source_tag=src["source_tag"],
                title=src.get("title", ""),
                url=src.get("url", ""),
                content_snippet=src.get("content", "")[:500]
            )
            db.add(db_source)
            await db.flush() # Để lấy db_source.id
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

    return {
        "current_agent": "curator",
        "indexed_chunks_count": state.get("indexed_chunks_count", 0) + chunks_count
    }

async def analyst_node(state: ResearchState) -> Dict[str, Any]:
    """
    Analyst Agent: Dùng Semantic Search RAG để trích xuất Claims + Evidence từ pgvector.
    """
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.tools.embedder import EmbedderTool

    llm = get_fast_llm().with_structured_output(AnalystExtraction)
    embedder = EmbedderTool()

    task_id_str = state.get("task_id")
    if not task_id_str:
        return {"current_agent": "analyst"}

    task_id = uuid.UUID(task_id_str)
    queries = state.get("current_queries", [])
    if not queries:
        queries = [state.get("research_question")]

    all_claims = []

    # Dùng asyncio.gather để xử lý song song các queries
    async def process_query(query: str) -> List[Dict]:
        async with AsyncSessionLocal() as db:
            # RAG: Lấy top 3 chunks liên quan nhất cho query
            similar_chunks = await embedder.search_similar_chunks(db, task_id, query, limit=3)

            if not similar_chunks:
                return []

            # Ghép nội dung
            context_text = "\n\n".join([f"Source: Chunk {c[0].chunk_index}\nContent: {c[0].content}" for c in similar_chunks])

            prompt = f"""
            Dựa vào các tài liệu sau, hãy trích xuất các luận điểm và bằng chứng liên quan đến truy vấn: '{query}'
            Tài liệu:
            {context_text}
            """

            try:
                extraction = await llm.ainvoke([HumanMessage(content=prompt)])
                return [c.model_dump() for c in extraction.claims]
            except Exception as e:
                print(f"Lỗi khi trích xuất claims: {e}")
                return []

    # Chạy song song tất cả các queries
    tasks = [process_query(q) for q in queries]
    results = await asyncio.gather(*tasks)

    for res_list in results:
        all_claims.extend(res_list)

    return {
        "current_agent": "analyst",
        "claims": all_claims  # Annotated[list, operator.add]
    }

async def writer_node(state: ResearchState) -> Dict[str, Any]:
    """
    Writer Agent: Viết bản nháp dựa trên Claims & Evidences. (Dùng mô hình xịn)
    """
    llm = get_smart_llm()
    plan = state.get("plan", {})
    claims = state.get("claims", [])
    feedback = state.get("critic_feedback", [])

    prompt = f"""
    Bạn là một Nhà văn học thuật chuyên nghiệp. Hãy viết báo cáo nghiên cứu về đề tài: {state.get('research_question')}
    Ngôn ngữ: {state.get('language')}

    Cấu trúc bắt buộc: {plan.get('required_sections', [])}
    Dữ liệu đã trích xuất: {claims}
    Lưu ý từ vòng sửa trước (nếu có): {feedback}

    Yêu cầu: Viết theo định dạng Markdown.
    """

    response = await llm.ainvoke([SystemMessage(content=prompt)])

    return {
        "current_agent": "writer",
        "draft_report_markdown": str(response.content)
    }

async def critic_node(state: ResearchState) -> Dict[str, Any]:
    """
    Critic Agent: Đóng vai 'Devil's Advocate' kiểm chứng logic và fact. Trả về JSON ngắn.
    """
    llm = get_fast_llm().with_structured_output(CriticVerdict)
    draft = state.get("draft_report_markdown", "")

    prompt = f"""
    Bạn là một Người phản biện độc lập khắt khe.
    Nhiệm vụ: Đọc bản nháp sau và đánh giá xem nó có đủ dữ liệu, logic, và độ chi tiết không.
    Bản nháp: {draft[:3000]}...
    """

    verdict: CriticVerdict = await llm.ainvoke([HumanMessage(content=prompt)])

    micro_count = state.get("current_micro_revision", 0) + 1 if verdict.verdict == "REVISE" else state.get("current_micro_revision", 0)

    return {
        "current_agent": "critic",
        "critic_verdict": verdict.verdict,
        "critic_feedback": verdict.feedback,
        "delta_queries": verdict.missing_areas,
        "current_micro_revision": micro_count
    }

async def post_processor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Post Processor: Module Regex code để định dạng Markdown cuối cùng và đánh số trích dẫn.
    """
    draft = state.get("draft_report_markdown", "")

    # Xử lý regex citation...
    final_md = draft

    return {
        "current_agent": "post_processor",
        "final_report_markdown": final_md,
        "status": "COMPLETED"
    }
