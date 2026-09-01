"""
models.py

Defines the SQL tables that persist what the agent did, so we have a
durable audit trail beyond just in-memory state (needed to show judges
after the run, and to compute batch-level metrics).

Tables:
- TransactionRecord: one row per input transaction + its final outcome
- AttemptLog: one row per action attempt (mirrors RecoveryState.history)
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class TransactionRecord(Base):
    """
    Function: stores the final result of running one transaction through
    the recovery graph — used to compute batch-level metrics (₹ recovered,
    escalation rate, etc).
    """
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)          # transaction_id
    customer_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    decline_code = Column(String, nullable=False)
    diagnosis = Column(String, nullable=True)
    final_status = Column(String, nullable=False)  # recovered/escalated/failed
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    attempts = relationship("AttemptLog", back_populates="transaction")


class AttemptLog(Base):
    """
    Function: stores each individual attempt (action + outcome) for a
    transaction — this IS the audit trail a judge can drill into per
    transaction_id.
    """
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, ForeignKey("transactions.id"))
    attempt_no = Column(Integer, nullable=False)
    action_taken = Column(String, nullable=False)
    outcome = Column(String, nullable=False)        # success/failed
    timestamp = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("TransactionRecord", back_populates="attempts")