"""
build_graphs.py

Function: build_recovery_graph() -> compiled LangGraph app

Wires the node functions from nodes.py into an actual graph: which node
runs first, and after check_node, where do we go next (loop back to retry,
escalate, or end)? This file is the "orchestration" layer — nodes.py has
no idea about routing, this file owns all of it.
"""

from langgraph.graph import StateGraph, END
from app.graph.state import RecoveryState
from app.graph.nodes import (
    diagnose_node,
    decide_node,
    act_node,
    check_node,
    escalate_node,
)


def _route_after_check(state: RecoveryState) -> str:
    """
    Function: the conditional edge after check_node. Reads state.status
    (set by check_node) and decides where the graph goes next. This is
    the stopping rule enforcement point — "retrying" only continues if
    check_node already confirmed attempt_count < max_attempts.
    """
    if state.status == "recovered":
        return "end"
    if state.status == "escalated":
        return "escalate"
    return "retry"  # status == "retrying"


def build_recovery_graph():
    """
    Function: assembles and compiles the graph.
    Flow: diagnose -> decide -> act -> check -> (decide | escalate | END)
    The loop back to "decide" is what lets the agent try a *different or
    repeated* action on subsequent attempts, bounded by max_attempts.
    """
    graph = StateGraph(RecoveryState)

    graph.add_node("diagnose", diagnose_node)
    graph.add_node("decide", decide_node)
    graph.add_node("act", act_node)
    graph.add_node("check", check_node)
    graph.add_node("escalate", escalate_node)

    graph.set_entry_point("diagnose")
    graph.add_edge("diagnose", "decide")
    graph.add_edge("decide", "act")
    graph.add_edge("act", "check")

    graph.add_conditional_edges(
        "check",
        _route_after_check,
        {
            "retry": "decide",
            "escalate": "escalate",
            "end": END,
        },
    )
    graph.add_edge("escalate", END)

    return graph.compile()