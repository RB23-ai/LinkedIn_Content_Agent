"""
agents/lead_detector.py
------------------------
Lead detection is mostly a deterministic keyword/regex pass (cheap, fast,
no LLM call needed for the common case) with an optional LLM agent for
ambiguous cases. This keeps costs down since comment volume can be high.
"""

import re
from crewai import Agent

DEFAULT_LEAD_KEYWORDS = [
    "dm me", "dm please", "price", "pricing", "demo", "book a call",
    "interested", "how much", "reach out", "send details", "sign me up",
]


def scan_comment_for_lead_keywords(comment_text: str, keywords: list[str] = None) -> str | None:
    """Fast, deterministic pass. Returns the matched keyword or None."""
    keywords = keywords or DEFAULT_LEAD_KEYWORDS
    text = comment_text.lower()
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            return kw
    return None


def create(llm):
    """
    LLM-backed agent for a second pass on comments that didn't match a
    keyword but might still be a soft lead (e.g. "wow didn't know this was
    possible for teams our size" -- interest without an obvious keyword).
    Use sparingly (e.g. only on comments over N words) to control LLM cost.
    """
    return Agent(
        role="Lead Qualification Analyst",
        goal="Read a LinkedIn comment and decide if it signals genuine buying "
             "interest, even without an obvious keyword like 'price' or 'DM me'",
        backstory=(
            "You've read thousands of B2B LinkedIn comments and can tell the "
            "difference between polite engagement ('great post!') and a "
            "comment that signals real interest in the product or service."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
