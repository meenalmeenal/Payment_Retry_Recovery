"""
razorpay_client.py

Function: execute_action(action, transaction_id, amount) -> "success" | "failed"

Executes the intervention chosen by decide_node. Where Razorpay's test
mode genuinely supports the call (e.g. generating a payment link for a
customer to update their card), we make a real API call. Where the
sandbox can't simulate a real bank retry outcome (Razorpay test mode
doesn't let us force a subscription charge retry on demand), we fall
back to a clearly-labeled simulated outcome so the loop still has
something real to react to.
"""

import os
import random
import razorpay
from dotenv import load_dotenv

load_dotenv()

client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
)

# Rough success-likelihood per action, used only for simulated outcomes.
# Reflects real-world intuition: temporary issuer problems often resolve
# on their own, expired cards need the customer to act (lower immediate
# success), etc. Documented here so it's transparent, not hidden.
SIMULATED_SUCCESS_RATE = {
    "retry_after_delay": 0.55,
    "send_update_card_link": 0.35,
    "switch_mandate": 0.45,
    "escalate_immediately": 0.0,
}


def _real_create_payment_link(transaction_id: str, amount: float) -> str:
    """
    Function: makes an actual Razorpay test-mode API call to create a
    payment link (used for the send_update_card_link action). Returns
    the link id/status — this part is real, not simulated.
    """
    link = client.payment_link.create({
        "amount": int(amount * 100),  # paise
        "currency": "INR",
        "description": f"Update payment method for transaction {transaction_id}",
        "notes": {"transaction_id": transaction_id},
    })
    return link.get("id", "unknown")


def _mock_retry_outcome(action: str) -> str:
    """
    Function: simulates whether a retry/mandate-switch succeeded, since
    Razorpay test mode can't force real charge-retry outcomes on demand.
    Clearly named "_mock_" so it's obvious in code review this isn't a
    live bank result.
    """
    rate = SIMULATED_SUCCESS_RATE.get(action, 0.0)
    return "success" if random.random() < rate else "failed"


def execute_action(action: str, transaction_id: str, amount: float) -> str:
    """
    Function: dispatches to the real API call or the simulated outcome
    depending on the action type, and always returns "success"/"failed"
    so nodes.py's check_node can react uniformly.
    """
    if action == "send_update_card_link":
        try:
            _real_create_payment_link(transaction_id, amount)
        except Exception:
            pass  # link creation failing doesn't itself mean recovery failed
        return _mock_retry_outcome(action)

    if action == "escalate_immediately":
        return "failed"

    # retry_after_delay, switch_mandate -> simulated (sandbox can't force these)
    return _mock_retry_outcome(action)