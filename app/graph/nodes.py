"""
nodes.py

Each function here is one node in the LangGraph. A node takes the current
RecoveryState, does one job, and returns a dict of fields to update on the
state. LangGraph merges that dict back into the state before routing to
the next node.

Flow: diagnose_node -> decide_node -> act_node -> check_node -> (loop back
to decide_node OR go to escalate_node OR end)
"""

from datetime import datetime
from app.graph.state import RecoveryState, AttemptRecord
from app.razorpay_client import execute_action
from app.llm import classify_decline_reason


# Maps a diagnosed root cause to the intervention we'll take.
# Kept as a simple lookup so the "why -> what to do" logic is transparent
# and easy to explain/justify to a judge (not a black-box LLM decision).
ACTION_MAP = {
    "temporary_issuer_problem": "retry_after_delay",
    "card_expired_or_invalid": "send_update_card_link",
    "insufficient_funds": "retry_after_delay",
    "mandate_revoked": "switch_mandate",
    "unknown": "escalate_immediately",
}


def diagnose_node(state: RecoveryState) -> dict:
    """
    Function: takes the raw decline_code and turns it into a root-cause
    category (diagnosis). Uses the LLM (Groq) to classify, since decline
    codes/messages can be messy or bank-specific text, not just clean enums.
    Updates: state.diagnosis, state.status = "diagnosing"
    """
    diagnosis = classify_decline_reason(state.decline_code)
    return {
        "diagnosis": diagnosis,
        "status": "diagnosing",
    }


def decide_node(state: RecoveryState) -> dict:
    """
    Function: looks up the diagnosis in ACTION_MAP to pick the intervention.
    This is the "decision" step — deliberately rule-based (not LLM) so the
    choice is explainable and deterministic given a diagnosis.
    Updates: state.action
    """
    action = ACTION_MAP.get(state.diagnosis, "escalate_immediately")
    return {"action": action}


def act_node(state: RecoveryState) -> dict:
    """
    Function: executes the chosen action. Calls out to razorpay_client,
    which either makes a real Razorpay test-mode API call (e.g. generating
    an update-card payment link) or, where the sandbox can't simulate a
    real retry outcome, returns a simulated success/failure so the loop
    still has something real to react to.
    Updates: nothing directly on state — result is consumed by check_node,
    but we increment attempt_count here since an attempt just happened.
    """
    outcome = execute_action(state.action, state.transaction_id, state.amount)
    record = AttemptRecord(
        attempt_no=state.attempt_count + 1,
        action_taken=state.action,
        outcome=outcome,
        timestamp=datetime.utcnow(),
    )
    return {
        "attempt_count": state.attempt_count + 1,
        "history": state.history + [record],
        "_last_outcome": outcome,  # transient field read by check_node/router
    }


def check_node(state: RecoveryState) -> dict:
    """
    Function: looks at the most recent attempt's outcome and decides the
    resulting status. Does NOT decide routing itself (that's the
    conditional edge in build_graphs.py) — it just updates state.status
    so the router has something clean to read.
    Updates: state.status -> "recovered", "retrying", or leaves as-is for
    the router to send to escalate.
    """
    last_outcome = state.history[-1].outcome if state.history else "failed"
    if last_outcome == "success":
        return {"status": "recovered"}
    if state.attempt_count >= state.max_attempts:
        return {"status": "escalated"}
    return {"status": "retrying"}


def escalate_node(state: RecoveryState) -> dict:
    """
    Function: terminal node for transactions that exhausted max_attempts
    without recovering. This is the stopping rule / bound in action —
    hands off to a human queue instead of retrying forever.
    Updates: state.status = "escalated" (idempotent, already set by check_node)
    """
    return {"status": "escalated"}