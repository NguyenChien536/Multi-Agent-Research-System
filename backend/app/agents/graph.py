from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from app.agents.state import ResearchState
from app.agents.nodes import (
    supervisor_node,
    researcher_node,
    curator_node,
    analyst_node,
    methodologist_node,
    experiment_runner_node,
    writer_node,
    critic_node,
    post_processor_node
)


async def plan_approval_wait_node(state: ResearchState) -> dict:
    """Persist an interrupt and release the worker until the user decides."""
    decision = interrupt({
        "kind": "PLAN_APPROVAL",
        "plan_version": state.get("plan_version", 0),
        "plan": state.get("plan", {}),
    })
    if not isinstance(decision, dict) or decision.get("plan_version") != state.get("plan_version", 0):
        raise ValueError("Plan approval decision does not match the active plan version")
    action = decision.get("action")
    if action == "REVISE_PLAN":
        return {
            "current_agent": "supervisor",
            "status": "RUNNING",
            "plan_approved": False,
            "plan": {},
            "plan_feedback": decision.get("feedback", ""),
        }
    if action != "APPROVE_PLAN":
        raise ValueError("Unsupported plan decision")
    return {
        "current_agent": "supervisor",
        "status": "RUNNING",
        "plan_approved": True,
        "plan": decision.get("plan", state.get("plan", {})),
        "plan_feedback": decision.get("feedback", state.get("plan_feedback")),
    }


def should_pause_for_plan_approval(state: ResearchState) -> str:
    """
    Định tuyến sau Supervisor:
    - Nếu require_plan_approval=True và chưa duyệt (plan_approved != True): Tạm dừng chờ duyệt.
    - Ngược lại: Chuyển thẳng sang Researcher.
    """
    if state.get("require_plan_approval") and not state.get("plan_approved"):
        return "plan_approval_wait"
    return "researcher"


async def wait_user_data_node(state: ResearchState) -> dict:
    """Persist an interrupt while human-led data collection happens outside ATI."""
    decision = interrupt({
        "kind": "USER_DATA",
        "plan_version": state.get("plan_version", 0),
        "research_type": state.get("research_type"),
    })
    if not isinstance(decision, dict) or decision.get("plan_version") != state.get("plan_version", 0):
        raise ValueError("Research data does not match the active plan version")
    return {
        "current_agent": "methodologist",
        "status": "RUNNING",
        "user_data_submission": decision.get("submission", {}),
    }


def route_after_plan_decision(state: ResearchState) -> str:
    return "researcher" if state.get("plan_approved") else "supervisor"


def route_after_user_data(state: ResearchState) -> str:
    if state.get("research_type") == "EMPIRICAL_COMPUTATIONAL":
        return "experiment_runner" if state.get("dataset_csv") else "wait_user_data"
    return "writer" if state.get("user_data_submission") else "wait_user_data"


def entry_route(state: ResearchState) -> str:
    return "writer" if state.get("editorial_revision") else "supervisor"


def route_after_analyst(state: ResearchState) -> str:
    """
    Định tuyến sau Analyst:
    - Nếu research_type là EMPIRICAL_HUMAN hoặc EMPIRICAL_COMPUTATIONAL:
      chuyển sang Methodologist để thiết lập đề cương và phương pháp nghiên cứu.
    - Ngược lại (REVIEW): chuyển thẳng sang Writer.
    """
    rtype = state.get("research_type", "REVIEW")
    if rtype in ("EMPIRICAL_HUMAN", "EMPIRICAL_COMPUTATIONAL"):
        return "methodologist"
    return "writer"


def route_after_methodologist(state: ResearchState) -> str:
    """
    Định tuyến sau Methodologist:
    - Nếu nghiên cứu thực nghiệm cần dữ liệu ngoài hệ thống mà chưa có:
      tạm dừng tại wait_user_data (trả về worker, giải phóng worker lease).
    - Nếu EMPIRICAL_COMPUTATIONAL có dataset CSV người dùng đã tải lên:
      chuyển sang Experiment Runner để chạy pipeline thực nghiệm tính toán.
    - Ngược lại (đã có user_data_submission hoặc là dạng bài khác):
      chuyển sang Writer để viết bài báo hoàn chỉnh.
    """
    if state.get("research_type") == "EMPIRICAL_HUMAN" and not state.get("user_data_submission"):
        return "wait_user_data"
    if state.get("research_type") == "EMPIRICAL_COMPUTATIONAL":
        if not state.get("dataset_csv"):
            return "wait_user_data"
        return "experiment_runner"
    return "writer"


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


def build_research_graph(checkpointer=None) -> StateGraph:
    """
    Biên dịch StateGraph cho Multi-Agent Research System.
    """
    workflow = StateGraph(ResearchState)

    # 1. Khai báo các Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("plan_approval_wait", plan_approval_wait_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("curator", curator_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("methodologist", methodologist_node)
    workflow.add_node("experiment_runner", experiment_runner_node)
    workflow.add_node("wait_user_data", wait_user_data_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("post_processor", post_processor_node)
    workflow.add_node("macro_routing", macro_routing_node)

    # 2. Định nghĩa các Edges (Luồng đi)
    workflow.set_conditional_entry_point(entry_route, {"supervisor":"supervisor", "writer":"writer"})

    # Supervisor -> Rẽ nhánh: Chờ duyệt (HITL) hoặc Tiếp tục nghiên cứu
    workflow.add_conditional_edges(
        "supervisor",
        should_pause_for_plan_approval,
        {
            "plan_approval_wait": "plan_approval_wait",
            "researcher": "researcher",
        }
    )
    workflow.add_conditional_edges(
        "plan_approval_wait",
        route_after_plan_decision,
        {"researcher": "researcher", "supervisor": "supervisor"},
    )

    # Researcher -> Curator -> Analyst
    workflow.add_edge("researcher", "curator")
    workflow.add_edge("curator", "analyst")

    # Analyst -> Rẽ nhánh: Methodologist (Empirical) hoặc Writer (Review)
    workflow.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {
            "methodologist": "methodologist",
            "writer": "writer",
        },
    )

    # Methodologist -> Rẽ nhánh: Chờ dữ liệu thực tế, Thí nghiệm tính toán, hoặc Viết bài
    workflow.add_conditional_edges(
        "methodologist",
        route_after_methodologist,
        {
            "wait_user_data": "wait_user_data",
            "experiment_runner": "experiment_runner",
            "writer": "writer",
        },
    )
    workflow.add_conditional_edges(
        "wait_user_data",
        route_after_user_data,
        {"writer": "writer", "experiment_runner": "experiment_runner", "wait_user_data": "wait_user_data"},
    )
    workflow.add_edge("experiment_runner", "writer")

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

    return workflow.compile(checkpointer=checkpointer)

# Khởi tạo graph instance để Worker có thể import
research_graph = build_research_graph()
