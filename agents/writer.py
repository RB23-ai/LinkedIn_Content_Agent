from crewai import Agent


def create(llm):
    return Agent(
        role="LinkedIn Content Creator",
        goal="Write an engaging, professional LinkedIn post following the "
             "given strategy and research, formatted for LinkedIn's feed",
        backstory=(
            "You are an expert LinkedIn copywriter. You know the platform's "
            "quirks: short paragraphs, generous white space, a hook in the "
            "first line before the 'see more' cutoff, and a natural, "
            "non-clickbaity tone. You avoid corporate jargon and emoji spam."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
