"""
sessions.py

Function: get_session() -> SQLAlchemy session
Function: save_result(state) -> persists a finished RecoveryState to DB

Sets up the SQLite engine and provides the one function the rest of the
app needs to call after a transaction finishes running through the graph:
write its final record + full attempt history to disk.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, TransactionRecord, AttemptLog
from app.graph.state import RecoveryState

engine = create_engine("sqlite:///data/recovery.db")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Function: returns a new DB session for use in a `with` block or manual close."""
    return SessionLocal()


def save_result(state: RecoveryState) -> None:
    """
    Function: takes a finished RecoveryState (after the graph has run to
    completion for one transaction) and writes it to the transactions +
    attempts tables. Called once per transaction after graph.invoke().
    """
    session = get_session()
    try:
        record = TransactionRecord(
            id=state.transaction_id,
            customer_id=state.customer_id,
            amount=state.amount,
            decline_code=state.decline_code,
            diagnosis=state.diagnosis,
            final_status=state.status,
            attempt_count=state.attempt_count,
        )
        session.merge(record)  # merge = insert or update if already exists

        for a in state.history:
            session.add(AttemptLog(
                transaction_id=state.transaction_id,
                attempt_no=a.attempt_no,
                action_taken=a.action_taken,
                outcome=a.outcome,
                timestamp=a.timestamp,
            ))

        session.commit()
    finally:
        session.close()