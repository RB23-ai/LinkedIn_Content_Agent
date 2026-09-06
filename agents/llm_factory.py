"""
agents/llm_factory.py
----------------------
Central place to build the LLM object so every agent uses the same
configuration. Defaults to Groq (fast, generous free tier); falls back
to a local Ollama model if no GROQ_API_KEY is set.
"""

import os
from langchain_groq import ChatGroq


def get_llm():
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return ChatGroq(
            api_key=groq_key,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )

    # Local fallback via Ollama (no API key needed, runs on your machine)
    from langchain_community.chat_models import ChatOllama
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.7,
    )
