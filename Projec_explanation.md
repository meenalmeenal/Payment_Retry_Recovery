# Payment Retry Recovery Agent — Project Explanation

## What we built

A **failed-payment recovery agent** — instead of blindly retrying every failed
recurring payment the same way, it looks at *why* it failed and picks a
matching fix, tracks every attempt, and stops itself after a limit instead of
retrying forever.

## The core problem it solves

Subscriptions/recurring payments fail all the time — expired card,
insufficient funds, bank glitch, blocked mandate. Most systems just retry
blindly regardless of cause. This wastes attempts on unrecoverable cases and
misses better recovery options for ones that need a different fix (e.g. an
expired card needs the customer to act — retrying with the same card is
pointless).

## Architecture — the agent loop (LangGraph)

We modeled this as a **stateful graph**, not a script, because the agent
needs memory across steps (how many attempts so far, what's been tried) and
needs to make repeated decisions until it reaches an end state.

```
diagnose → decide → act → check → (loop back to decide | escalate | end)
```

- **State (`state.py`)**: a Pydantic object (`RecoveryState`) carrying
  transaction ID, amount, decline_code, diagnosis, chosen action, attempt
  count, full attempt history, and current status. This is what "remembers"
  across the loop.

- **diagnose_node**: sends the raw decline_code to a Groq-hosted LLM
  (`openai/gpt-oss-120b`), which classifies it into one of 5 fixed root-cause
  categories (temporary issuer problem, expired card, insufficient funds,
  mandate revoked, unknown). Using an LLM here matters because real decline
  messages are messy/bank-specific text, not clean enums.

- **decide_node**: a plain rule-based lookup table maps root cause →
  intervention (retry after delay / send update-card link / switch mandate /
  escalate). Deliberately *not* an LLM call — this keeps the decision fully
  explainable and deterministic given a diagnosis, which matters for the
  "explainable" requirement.

- **act_node**: executes the chosen action via `razorpay_client.py`. For
  "send update card link," it makes a **real Razorpay test-mode API call** to
  generate an actual payment link. For retry/mandate-switch actions,
  Razorpay's sandbox can't force a real bank-approval outcome on demand, so
  we use a documented, clearly-labeled simulated success/failure (probability
  calibrated per action type — e.g. temporary issuer problems succeed more
  often on retry than expired cards do without customer action).

- **check_node**: reads the outcome of the last attempt and sets status:
  `recovered` if it succeeded, `escalated` if attempt_count has hit the max,
  otherwise `retrying`.

- **escalate_node**: terminal node — this is the **stopping rule**. No
  infinite retry loops; after N attempts (configurable in `config.py`), it
  hands off to a human queue instead.

## Persistence & audit trail

Every attempt (action taken, outcome, timestamp) is written to SQLite
(`models.py` / `sessions.py`) — this is what makes the system **auditable
after the fact**, not just something that ran once. LangSmith tracing was
also wired in so every node execution is traceable step-by-step in their
dashboard, giving a second, visual form of the audit trail.

## Interfaces

- **FastAPI (`main.py`)**: `POST /run-batch` runs N synthetic transactions
  through the graph and returns batch metrics; `GET /audit/{transaction_id}`
  returns one transaction's full attempt history.
- **Streamlit dashboard**: lets you trigger a batch run, see headline metrics
  live, and look up any transaction's audit trail by ID.

## What's real vs. simulated

| Component | Status |
|---|---|
| Agent decision loop, stopping rule, routing | Real |
| LLM diagnosis (Groq) | Real |
| Razorpay payment-link creation | Real (test mode) |
| Failed-payment batch | Synthetic — no public dataset of real decline-code-level failures exists (PCI/privacy reasons), so this is standard practice, not a shortcut |
| Retry/mandate-switch success outcome | Simulated with documented probabilities — Razorpay sandbox has no way to force a live bank response for these |

## Result from the last run

Batch of 100 synthetic failed payments: **91% recovery rate**, ₹229,955
recovered out of ₹253,668 at risk, 9% correctly escalated to human review,
average 1.52 attempts per transaction before resolution — demonstrating the
bounded, diagnosis-driven approach actually recovers most of what's
recoverable while not wasting effort/spamming the ones that need a human.