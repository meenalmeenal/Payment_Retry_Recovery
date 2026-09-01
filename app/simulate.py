"""
simulate.py

Function: generate_batch(n) -> list[dict]

Creates a synthetic batch of failed payment transactions with randomly
assigned decline codes, so we have something to run the recovery graph
against and measure results on (money recovered / at risk, etc).
"""

import random
import uuid

DECLINE_CODES = [
    "insufficient_funds",
    "expired_card",
    "issuer_down",
    "do_not_honor",
    "invalid_cvv",
]

# Rough weighting so the batch looks realistic, not uniform-random.
DECLINE_WEIGHTS = [0.35, 0.20, 0.15, 0.20, 0.10]


def generate_batch(n: int = 50) -> list[dict]:
    """
    Function: builds n synthetic failed-payment records, each with a
    unique transaction_id, a customer_id, a random amount, and a decline
    code drawn from DECLINE_CODES per DECLINE_WEIGHTS.
    Returns: list of plain dicts (later used to construct RecoveryState).
    """
    batch = []
    for _ in range(n):
        batch.append({
            "transaction_id": f"txn_{uuid.uuid4().hex[:10]}",
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "amount": round(random.uniform(199, 4999), 2),
            "decline_code": random.choices(DECLINE_CODES, weights=DECLINE_WEIGHTS)[0],
        })
    return batch


if __name__ == "__main__":
    import csv

    data = generate_batch(50)
    with open("data/failed_payments_batch.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["transaction_id", "customer_id", "amount", "decline_code"])
        writer.writeheader()
        writer.writerows(data)
    print(f"Generated {len(data)} synthetic failed payments -> data/failed_payments_batch.csv")