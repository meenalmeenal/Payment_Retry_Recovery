# Payment Retry Recovery Agent

Detects failed recurring payments, diagnoses the root cause, chooses a
bounded recovery action, executes it (real Razorpay test-mode calls where
supported, simulated bank outcomes where sandbox can't force them), and
measures ₹ recovered across a batch — with a full per-transaction audit trail.

## Setup

```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows
# source venv/bin/activate         # Mac/Linux

pip install -r requirements.txt
cp .env.example .env               # then fill in your real keys

mkdir data
type nul > app\__init__.py         # Windows; use `touch` on Mac/Linux
type nul > app\db\__init__.py
type nul > app\graph\__init__.py
```

Required keys in `.env`:
- `GROQ_API_KEY` — free at console.groq.com
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — test-mode keys from Razorpay dashboard
- `LANGCHAIN_API_KEY` (optional) — free at smith.langchain.com, enables trace-based audit view

## Run

Terminal 1 — API server:
```bash
uvicorn app.main:app --reload
```

Terminal 2 — dashboard:
```bash
streamlit run streamlit_app.py
```

Open the Streamlit URL, click "Run batch" to generate synthetic failed
payments and run them through the recovery agent, then paste any
transaction_id to see its full attempt-by-attempt audit trail.

## How it works

```
diagnose -> decide -> act -> check -> (loop to decide | escalate | end)
```

- **diagnose**: Groq LLM classifies the decline code into a root cause
- **decide**: rule-based lookup maps root cause -> intervention (explainable, not a black box)
- **act**: executes the action (real Razorpay payment-link call for card updates;
  simulated success/failure for retry/mandate actions, since test mode can't
  force real bank outcomes on demand — clearly labeled `_mock_` in code)
- **check**: reads the outcome, decides recovered / retry / escalate
- **escalate**: stopping rule — max attempts (see `config.py`) hands off to a human queue

Every attempt is logged to SQLite (`data/recovery.db`) and, if LangSmith
is configured, auto-traced there too — this is the audit trail.

## What's real vs simulated

| Part | Real or simulated |
|---|---|
| Agent loop / decisions / stopping rule | Real |
| Groq LLM classification | Real |
| Razorpay payment-link creation | Real (test mode) |
| Failed-payment batch | Synthetic (no public dataset exists for this) |
| Retry/mandate success outcome | Simulated (test mode can't force bank retry results) |