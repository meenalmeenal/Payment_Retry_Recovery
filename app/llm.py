"""
llm.py

Function: classify_decline_reason(decline_code) -> root cause category

Wraps a Groq LLM call that takes a raw decline_code/message (which can be
messy, bank-specific text) and maps it to one of a small fixed set of root
cause categories that nodes.py's ACTION_MAP knows how to handle.

We constrain the output to a fixed set via prompt instructions so the
result is always one of the known categories the rest of the graph can
route on deterministically.
"""

import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

VALID_CATEGORIES = [
    "temporary_issuer_problem",
    "card_expired_or_invalid",
    "insufficient_funds",
    "mandate_revoked",
    "unknown",
]

_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

_SYSTEM_PROMPT = f"""You classify a payment decline code into exactly one
of these categories: {", ".join(VALID_CATEGORIES)}.
Reply with ONLY the category string, nothing else."""


def classify_decline_reason(decline_code: str) -> str:
    """
    Function: sends decline_code to the LLM, returns a validated category.
    Falls back to "unknown" if the LLM returns something outside the
    allowed set, so downstream routing never breaks on a bad response.
    """
    response = _llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": decline_code},
    ])
    category = response.content.strip()
    return category if category in VALID_CATEGORIES else "unknown"