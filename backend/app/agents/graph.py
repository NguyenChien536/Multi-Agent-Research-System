from langgraph.graph import StateGraph, END
from app.agents.state import ResearchState
from app.agents.nodes import (
    supervisor_node,
    researcher_node,
    curator_node,
    analyst_node,
    writer_node,
    critic_node,
    post_processor_node
)


async def macro_routing_node(state: ResearchState) -> dict:
    """Điểm định tuyến tường minh trước khi quyết định có tìm thêm nguồn hay không."""
    return {"current_agent": "macro_routing", "current_micro_revision": 0}

def should_continue_research(state: ResearchState) -> str:
    """
    Routing logic: Macro-loop.
    Quyết định bằng code Python deterministic.
    """
    if state.get("critic_verdict") == "NEED_MORE_DATA":
        budget = state.get("budget") or {}
        max_iterations = state.get("max_iterations", budget.get("max_iterations", 2))
        if state.get("current_iteration", 0) < max_iterations:
            return "researcher"
    return "post_processor"

def should_revise_draft(state: ResearchState) -> str:
    """
    Routing logic: Micro-loop.
    Quyết định bằng code Python deterministic.
    """
    if state.get("critic_verdict") == "REVISE":
        if state.get("current_micro_revision", 0) < state.get("max_micro_revisions", 2):
            return "writer"

    if state.get("critic_verdict") == "NEED_MORE_DATA":
        return "macro_routing"

    return "post_processor"

def build_research_graph() -> StateGraph:
    """
    Biên dịch StateGraph cho Multi-Agent Research System.
    """
    workflow = StateGraph(ResearchState)

    # 1. Khai báo các Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("curator", curator_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("post_processor", post_processor_node)
    workflow.add_node("macro_routing", macro_routing_node)

    # 2. Định nghĩa các Edges (Luồng đi)
    workflow.set_entry_point("supervisor")

    # Supervisor -> Researcher (Bỏ qua nhánh HITL tạm thời)
    workflow.add_edge("supervisor", "researcher")

    # Researcher -> Curator -> Analyst -> Writer
    workflow.add_edge("researcher", "curator")
    workflow.add_edge("curator", "analyst")
    workflow.add_edge("analyst", "writer")

    # Writer -> Critic (Bắt đầu Micro-loop)
    workflow.add_edge("writer", "critic")

    # Critic -> Conditional Edge
    workflow.add_conditional_edges(
        "critic",
        should_revise_draft,
        {
            "writer": "writer",                   # Micro-loop: Sửa lại Draft
            "macro_routing": "macro_routing",     # Cần chuyển hướng Macro-loop
            "post_processor": "post_processor"    # PASS -> Xuất bản
        }
    )

    # Điểm định tuyến được đăng ký rõ ràng trong graph.
    workflow.add_conditional_edges(
        "macro_routing",
        should_continue_research,
        {
            "researcher": "researcher",
            "post_processor": "post_processor"
        }
    )

    # Post Processor -> Kết thúc
    workflow.add_edge("post_processor", END)

    return workflow.compile()

# Khởi tạo graph instance để Worker có thể import
research_graph = build_research_graph()
