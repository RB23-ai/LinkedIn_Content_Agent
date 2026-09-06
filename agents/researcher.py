import os
from crewai import Agent


def create(llm):
    tools = []
    if os.getenv("TAVILY_API_KEY"):
        # Import lazily so the app still runs without crewai-tools' search
        # extras installed if the user has no Tavily key.
        from crewai_tools import TavilySearchTool
        tools.append(TavilySearchTool())

    return Agent(
        role="Research Analyst",
        goal="Gather factual, up-to-date information, statistics, and expert "
             "viewpoints on a given topic, with sources noted",
        backstory=(
            "You are a meticulous B2B research analyst. You dig up recent "
            "statistics, named studies, and credible expert quotes rather "
            "than vague generalities. You always note where a fact came "
            "from so the writer can reference it responsibly."
        ),
        tools=tools,
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
