"""
main.py

FastAPI entrypoint. Exposes:
- POST /run-batch: generates (or loads) a batch of failed payments, runs
  each through the recovery graph, persists results, returns summary metrics.
- GET /audit/{transaction_id}: returns the full attempt history for one
  transaction, from the DB.

This is the layer a judge/demo can hit directly, or that streamlit_app.py
calls into.
"""

from fastapi import FastAPI, HTTPException
from app.graph.build_graphs import build_recovery_graph
from app.graph.state import RecoveryState
from app.db.sessions import save_result, get_session
from app.db.models import TransactionRecord, AttemptLog
from app.simulate import generate_batch

app = FastAPI(title="Payment Retry Recovery Agent")
recovery_graph = build_recovery_graph()


@app.post("/run-batch")
def run_batch(n: int = 50):
    """
    Function: generates n synthetic failed payments, runs each through
    the compiled LangGraph to completion, saves each result to DB, and
    returns batch-level metrics (recovery rate, ₹ recovered/at risk, etc).
    """
    batch = generate_batch(n)
    results = []

    for txn in batch:
        initial_state = RecoveryState(**txn)
        final_state_dict = recovery_graph.invoke(initial_state)
        final_state = RecoveryState(**final_state_dict)
        save_result(final_state)
        results.append(final_state)

    total_at_risk = sum(r.amount for r in results)
    recovered = [r for r in results if r.status == "recovered"]
    total_recovered = sum(r.amount for r in recovered)
    escalated = [r for r in results if r.status == "escalated"]

    return {
        "batch_size": len(results),
        "total_at_risk": round(total_at_risk, 2),
        "total_recovered": round(total_recovered, 2),
        "recovery_rate_pct": round(100 * len(recovered) / len(results), 2) if results else 0,
        "escalation_rate_pct": round(100 * len(escalated) / len(results), 2) if results else 0,
        "avg_attempts": round(sum(r.attempt_count for r in results) / len(results), 2) if results else 0,
    }


@app.get("/audit/{transaction_id}")
def get_audit(transaction_id: str):
    """
    Function: fetches one transaction's final record plus its full
    attempt-by-attempt history from the DB — this is the "show the audit
    trail" requirement made queryable.
    """
    session = get_session()
    try:
        record = session.get(TransactionRecord, transaction_id)
        if not record:
            raise HTTPException(status_code=404, detail="Transaction not found")

        attempts = (
            session.query(AttemptLog)
            .filter(AttemptLog.transaction_id == transaction_id)
            .order_by(AttemptLog.attempt_no)
            .all()
        )

        return {
            "transaction_id": record.id,
            "customer_id": record.customer_id,
            "amount": record.amount,
            "decline_code": record.decline_code,
            "diagnosis": record.diagnosis,
            "final_status": record.final_status,
            "attempts": [
                {
                    "attempt_no": a.attempt_no,
                    "action_taken": a.action_taken,
                    "outcome": a.outcome,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in attempts
            ],
        }
    finally:
        session.close()