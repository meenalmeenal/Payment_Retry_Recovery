# Payment Retry Recovery Agent

Detects failed recurring payments, diagnoses the root cause, chooses a
bounded recovery action, executes it (real Razorpay test-mode calls where
supported, simulated bank outcomes where sandbox can't force them), and
measures ₹ recovered across a batch — with a full per-transaction audit trail.

## Setup

### 1. Create and activate virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create required folders/files

**Windows (PowerShell):**
```powershell
mkdir data
New-Item app\__init__.py
New-Item app\db\__init__.py
New-Item app\graph\__init__.py
```

**Mac/Linux:**
```bash
mkdir data
touch app/__init__.py app/db/__init__.py app/graph/__init__.py
```

### 4. Create `.env` file in project root

Create a file named `.env` (copy `.env.example` if present) and fill in:

```
GROQ_API_KEY=your_groq_api_key_here
RAZORPAY_KEY_ID=your_razorpay_test_key_id
RAZORPAY_KEY_SECRET=your_razorpay_test_key_secret

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=payment-retry-recovery
```

**Where to get each key:**
- **GROQ_API_KEY** (required, free): go to https://console.groq.com → sign in → API Keys → Create API Key
- **RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET** (required, free, no KYC for test mode): go to https://dashboard.razorpay.com → sign up/log in → Settings → API Keys → Generate Test Key
- **LANGCHAIN_API_KEY** (optional, for trace-based audit view): go to https://smith.langchain.com → sign in → Settings → API Keys → Create API Key

## Run

**Terminal 1 — API server:**

Windows:
```powershell
uvicorn app.main:app --reload
```

Mac/Linux:
```bash
uvicorn app.main:app --reload
```
(same command on both — just make sure venv is activated in this terminal too)

**Terminal 2 — dashboard:**

Windows:
```powershell
streamlit run streamlit_app.py
```

Mac/Linux:
```bash
streamlit run streamlit_app.py
```
(again, activate venv in this terminal first — each new terminal needs its own activation)

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