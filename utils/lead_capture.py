"""
utils/lead_capture.py
-----------------------
Scans a batch of comments for a post and stores keyword-matched leads.
Deterministic keyword pass first (cheap); optionally escalate longer,
keyword-less comments to the LLM-based lead_detector agent.
"""

from agents.lead_detector import scan_comment_for_lead_keywords


def process_comments(db, workspace_id: int, post_id: int, comments: list[dict],
                      llm_agent=None, min_words_for_llm_check: int = 8) -> list[dict]:
    """
    comments: list of {"author": str, "text": str}
    Returns the list of leads that were captured.
    """
    captured = []
    for c in comments:
        text = c.get("text", "")
        author = c.get("author", "")

        matched_kw = scan_comment_for_lead_keywords(text)

        if not matched_kw and llm_agent and len(text.split()) >= min_words_for_llm_check:
            # Optional LLM escalation for longer comments with no obvious keyword.
            # Kept simple/sync here; wrap in a Task+Crew if you want full
            # CrewAI tracing on this step.
            verdict = llm_agent.execute_task_sync(text) if hasattr(llm_agent, "execute_task_sync") else None
            if verdict and "interest" in str(verdict).lower():
                matched_kw = "llm_detected_interest"

        if matched_kw:
            lead_id = db.add_lead(
                workspace_id=workspace_id,
                comment_text=text,
                matched_keyword=matched_kw,
                post_id=post_id,
                commenter_name=author,
            )
            captured.append({"id": lead_id, "author": author, "text": text, "keyword": matched_kw})

    return captured
