import os
import requests
from crewai import Agent
from crewai.tools import tool


@tool("Unsplash Image Search")
def search_unsplash(query: str) -> str:
    """Search Unsplash for a free stock photo matching the query.
    Returns up to 3 image URLs with attribution info."""
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key:
        return "No UNSPLASH_ACCESS_KEY configured -- skip image suggestions."
    resp = requests.get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": 3},
        headers={"Authorization": f"Client-ID {key}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return f"Unsplash search failed: {resp.status_code}"
    results = resp.json().get("results", [])
    if not results:
        return "No matching images found."
    lines = []
    for r in results:
        lines.append(
            f"- {r['urls']['regular']} (photo by {r['user']['name']}, "
            f"credit required per Unsplash license)"
        )
    return "\n".join(lines)


def create(llm):
    return Agent(
        role="Visual Content Curator",
        goal="Suggest a relevant, license-safe stock image or visual concept "
             "to accompany the LinkedIn post",
        backstory=(
            "You know that posts with a relevant, non-stock-y-looking image "
            "get more stops in the feed. You always respect Unsplash's "
            "attribution requirements and avoid cliche 'handshake' photos."
        ),
        tools=[search_unsplash],
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
