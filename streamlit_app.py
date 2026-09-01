"""
streamlit_app.py

Dashboard UI: lets you trigger a batch run against the FastAPI backend,
see summary metrics, a per-transaction results table, and drill into any
single transaction's audit trail.

Run with: streamlit run streamlit_app.py
(requires main.py's FastAPI server running separately, e.g.
 uvicorn app.main:app --reload)
"""

import streamlit as st
import requests
import pandas as pd

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Payment Retry Recovery Agent", layout="wide")
st.title("Payment Retry Recovery Agent")

# --- Run batch ---
st.subheader("Run a batch")
n = st.number_input("Batch size", min_value=1, max_value=500, value=50)

if st.button("Run batch"):
    with st.spinner("Running recovery agent over batch..."):
        response = requests.post(f"{API_BASE}/run-batch", params={"n": n})
    if response.status_code == 200:
        st.session_state["last_summary"] = response.json()
    else:
        st.error(f"Batch run failed: {response.text}")

# --- Summary metrics ---
if "last_summary" in st.session_state:
    summary = st.session_state["last_summary"]
    st.subheader("Batch summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total at risk", f"₹{summary['total_at_risk']:,}")
    col2.metric("Total recovered", f"₹{summary['total_recovered']:,}")
    col3.metric("Recovery rate", f"{summary['recovery_rate_pct']}%")
    col4.metric("Escalation rate", f"{summary['escalation_rate_pct']}%")

    st.caption(f"Average attempts per transaction: {summary['avg_attempts']}")

# --- Audit trail lookup ---
st.subheader("Audit trail lookup")
txn_id = st.text_input("Transaction ID")

if st.button("Fetch audit trail") and txn_id:
    response = requests.get(f"{API_BASE}/audit/{txn_id}")
    if response.status_code == 200:
        data = response.json()
        st.json({
            "customer_id": data["customer_id"],
            "amount": data["amount"],
            "decline_code": data["decline_code"],
            "diagnosis": data["diagnosis"],
            "final_status": data["final_status"],
        })
        if data["attempts"]:
            st.table(pd.DataFrame(data["attempts"]))
        else:
            st.info("No attempts logged for this transaction.")
    else:
        st.error("Transaction not found.")