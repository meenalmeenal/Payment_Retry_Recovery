"""
state.py

Defines RecoveryState — the single object that flows through every node
in the LangGraph. Each node reads fields from it and returns updates to it.
This is what makes the graph "stateful": attempt_count, status, and history
persist across the whole detect -> diagnose -> act -> check -> escalate loop.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime
from app.config import MAX_ATTEMPTS


class AttemptRecord(BaseModel):
    """One row of history: what we tried on a given attempt and what happened."""
    attempt_no: int
    action_taken: str
    outcome: Literal["success", "failed"]
    timestamp: datetime


class RecoveryState(BaseModel):
    # --- identity / input ---
    transaction_id: str
    customer_id: str
    amount: float
    decline_code: str                     # e.g. "insufficient_funds", "expired_card"

    # --- working memory, updated as the graph runs ---
    diagnosis: Optional[str] = None       # root cause category from diagnose_node
    action: Optional[str] = None          # chosen intervention from decide_node
    attempt_count: int = 0                # incremented each retry loop
    max_attempts: int = Field(default_factory=lambda: MAX_ATTEMPTS)  # stopping rule / bound
    history: List[AttemptRecord] = []     # full audit trail for this transaction

    # --- final outcome ---
    status: Literal[
        "pending",     # not yet processed
        "diagnosing",  # mid-graph
        "retrying",    # loop back for another attempt
        "recovered",   # money got recovered
        "escalated",   # hit max_attempts, handed to human
        "failed"       # terminal failure (no more retries, not recovered)
    ] = "pending"