"""
utils/crew_runner.py
----------------------
Composes the full CrewAI pipeline (research -> strategy -> write -> edit
-> hashtags/image -> optional competitor benchmarking) for ONE workspace's
post request. Kept out of app.py so the Streamlit file stays UI-focused.
"""

from crewai import Crew, Process

from agents.llm_factory import get_llm
from agents import researcher, strategist, writer, editor, hashtag_agent, image_agent, competitor_benchmarker
from tasks import definitions as tasks


def generate_post(topic: str, vector_store=None, workspace_id: int = None,
                   competitor_name: str = None) -> dict:
    """
    Runs the full pipeline and returns a dict:
      { "post": str, "hashtags": str, "image_suggestion": str,
        "competitor_feedback": str | None }
    """
    llm = get_llm()

    research_agent = researcher.create(llm)
    strategy_agent = strategist.create(llm)
    write_agent = writer.create(llm)
    edit_agent = editor.create(llm)
    tag_agent = hashtag_agent.create(llm)
    img_agent = image_agent.create(llm)

    research_task = tasks.create_research_task(research_agent, topic)
    strategy_task = tasks.create_strategy_task(strategy_agent, topic, research_task)
    writing_task = tasks.create_writing_task(write_agent, strategy_task, research_task)
    editor_task = tasks.create_editor_task(edit_agent, writing_task)
    hashtag_task = tasks.create_hashtag_task(tag_agent, editor_task, topic)
    image_task = tasks.create_image_task(img_agent, editor_task, topic)

    task_list = [research_task, strategy_task, writing_task, editor_task, hashtag_task, image_task]
    agent_list = [research_agent, strategy_agent, write_agent, edit_agent, tag_agent, img_agent]

    competitor_task = None
    if vector_store and workspace_id:
        competitor_posts = vector_store.get_top_competitor_posts(
            workspace_id, competitor_name=competitor_name, top_k=3
        )
        if competitor_posts:
            bench_agent = competitor_benchmarker.create(llm)
            competitor_text = "\n---\n".join(p["text"] for p in competitor_posts)
            competitor_task = tasks.create_competitor_analysis_task(
                bench_agent, editor_task, competitor_text
            )
            task_list.append(competitor_task)
            agent_list.append(bench_agent)

    crew = Crew(
        agents=agent_list,
        tasks=task_list,
        process=Process.sequential,
        verbose=True,
    )
    crew.kickoff()

    return {
        "post": str(editor_task.output),
        "hashtags": str(hashtag_task.output),
        "image_suggestion": str(image_task.output),
        "competitor_feedback": str(competitor_task.output) if competitor_task else None,
    }
