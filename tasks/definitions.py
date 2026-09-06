"""
tasks/definitions.py
---------------------
Task factory functions for the CrewAI pipeline. Kept separate from
agents/ so app.py can compose different pipelines (e.g. skip the image
agent) without touching agent definitions.
"""

from crewai import Task


def create_research_task(agent, topic: str) -> Task:
    return Task(
        description=(
            f"Research the topic: '{topic}'. Find 2-3 recent statistics "
            f"(with rough source/year), one expert viewpoint or notable "
            f"case study, and one contrarian or lesser-known angle."
        ),
        expected_output="A short research brief (bullet points) with sources noted inline.",
        agent=agent,
    )


def create_strategy_task(agent, topic: str, research_task: Task) -> Task:
    return Task(
        description=(
            f"Using the research brief for topic '{topic}', define: "
            f"(1) the hook angle for the opening line, (2) the post structure "
            f"(e.g. story -> insight -> data -> CTA), (3) target audience, "
            f"(4) the call to action."
        ),
        expected_output="A strategic content brief covering hook, structure, audience, and CTA.",
        agent=agent,
        context=[research_task],
    )


def create_writing_task(agent, strategy_task: Task, research_task: Task) -> Task:
    return Task(
        description=(
            "Write a LinkedIn post following the strategy brief and using "
            "facts from the research brief. Include: a strong 1-2 line hook, "
            "3-4 short paragraphs with generous white space, one concrete "
            "statistic, and a question or CTA at the end. Do not include "
            "hashtags -- those are added separately."
        ),
        expected_output="A draft LinkedIn post, ready for editing, with no hashtags.",
        agent=agent,
        context=[strategy_task, research_task],
    )


def create_editor_task(agent, writing_task: Task) -> Task:
    return Task(
        description=(
            "Review and polish the draft post: tighten sentences, fix any "
            "grammar issues, make sure the tone is natural (not corporate "
            "jargon), and confirm there's a genuine CTA at the end. Return "
            "ONLY the final post text."
        ),
        expected_output="The final, polished LinkedIn post text.",
        agent=agent,
        context=[writing_task],
    )


def create_hashtag_task(agent, editor_task: Task, topic: str) -> Task:
    return Task(
        description=(
            f"Based on the final post about '{topic}', suggest 4-6 hashtags: "
            f"1-2 broad/industry tags and 2-4 specific/niche tags."
        ),
        expected_output="A list of 4-6 hashtags, each starting with #.",
        agent=agent,
        context=[editor_task],
    )


def create_image_task(agent, editor_task: Task, topic: str) -> Task:
    return Task(
        description=(
            f"Suggest a relevant stock image concept (and search for one via "
            f"the Unsplash tool if available) for a LinkedIn post about "
            f"'{topic}'. Avoid cliche imagery."
        ),
        expected_output="1-3 image URLs with attribution, or a visual concept description.",
        agent=agent,
        context=[editor_task],
    )


def create_competitor_analysis_task(agent, editor_task: Task, competitor_posts: str) -> Task:
    return Task(
        description=(
            f"Compare the final post against these competitor posts:\n"
            f"{competitor_posts}\n"
            f"Suggest 2-4 concrete, specific improvements (not generic advice)."
        ),
        expected_output="A short list of specific, actionable improvement suggestions.",
        agent=agent,
        context=[editor_task],
    )
