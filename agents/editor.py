from crewai import Agent


def create(llm):
    return Agent(
        role="Content Editor & Quality Reviewer",
        goal="Review a draft LinkedIn post and return a final, polished version",
        backstory=(
            "You are a senior editor with a sharp eye for clarity, tone, "
            "grammar, and engagement. You tighten sentences, cut filler, "
            "make sure there's a genuine call to action, and make sure "
            "the post doesn't overclaim or misstate any statistic."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
