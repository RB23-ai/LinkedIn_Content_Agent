"""
app.py
-------
Main Streamlit application. Every page reads/writes data scoped to the
currently selected workspace (company) via `st.session_state.workspace_id`.
"""

import os
import streamlit as st
from dotenv import load_dotenv

from utils.database import Database
from utils.vector_store import VectorStore
from utils.linkedin_publisher import LinkedInAPI, LinkedInAPIError, register_manual_competitor_post
from utils.sharing_utils import generate_share_bundle, post_to_slack
from utils.crew_runner import generate_post
from utils.scheduler import start_scheduler

load_dotenv()

st.set_page_config(page_title="LinkedIn AI Strategist", page_icon="🚀", layout="wide")

# ---------------------------------------------------------------------
# Singletons (cached so we don't reconnect to SQLite/Chroma every rerun)
# ---------------------------------------------------------------------
@st.cache_resource
def get_db():
    return Database()

@st.cache_resource
def get_vector_store():
    return VectorStore()

db = get_db()
vs = get_vector_store()

if "scheduler_started" not in st.session_state:
    start_scheduler(hour=8, minute=0)
    st.session_state.scheduler_started = True

# ---------------------------------------------------------------------
# Sidebar: workspace switcher
# ---------------------------------------------------------------------
st.sidebar.title("🏢 Workspace")

workspaces = db.get_workspaces()
workspace_names = {ws["name"]: ws["id"] for ws in workspaces}

with st.sidebar.expander("➕ Add new company"):
    new_name = st.text_input("Company name", key="new_ws_name")
    new_industry = st.text_input("Industry (optional)", key="new_ws_industry")
    if st.button("Create workspace"):
        if new_name.strip():
            wid = db.create_workspace(new_name.strip(), new_industry.strip())
            st.success(f"Created workspace '{new_name}'")
            st.rerun()
        else:
            st.warning("Enter a company name first.")

if not workspaces:
    st.info("👋 Create your first company workspace in the sidebar to get started.")
    st.stop()

selected_name = st.sidebar.selectbox("Active company", list(workspace_names.keys()))
workspace_id = workspace_names[selected_name]
st.session_state.workspace_id = workspace_id

page = st.sidebar.radio(
    "Navigate",
    ["💡 Ideas", "✍️ Post Editor", "📅 Calendar", "📊 Analytics",
     "🔍 Competitors", "🎯 Leads", "⚙️ Settings"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Every page only reads/writes data for the selected workspace.")

# ---------------------------------------------------------------------
# Page: Ideas
# ---------------------------------------------------------------------
if page == "💡 Ideas":
    st.header(f"Content Ideas — {selected_name}")

    with st.form("new_idea_form"):
        title = st.text_input("Idea title")
        desc = st.text_area("Description / angle")
        score = st.slider("Estimated engagement potential", 1, 10, 5)
        submitted = st.form_submit_button("Add idea")
        if submitted and title.strip():
            db.add_idea(workspace_id, title.strip(), desc.strip(), score)
            st.rerun()

    ideas = db.get_ideas(workspace_id)
    if not ideas:
        st.info("No ideas yet -- add one above.")
    for idea in ideas:
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
        col1.markdown(f"**{idea['title']}** ({idea['status']})  \n{idea['description']}")
        col2.metric("Score", idea["score"])
        if col3.button("Approve", key=f"approve_{idea['id']}"):
            db.update_idea_status(idea["id"], workspace_id, "approved")
            st.rerun()
        if col4.button("Reject", key=f"reject_{idea['id']}"):
            db.update_idea_status(idea["id"], workspace_id, "rejected")
            st.rerun()

# ---------------------------------------------------------------------
# Page: Post Editor (the agent pipeline)
# ---------------------------------------------------------------------
elif page == "✍️ Post Editor":
    st.header(f"Generate a Post — {selected_name}")

    topic = st.text_input("Topic / idea to write about")
    competitors = db.get_competitors(workspace_id)
    competitor_choice = st.selectbox(
        "Benchmark against competitor (optional)",
        ["None"] + [c["name"] for c in competitors],
    )

    if st.button("🚀 Generate with AI agents", type="primary", disabled=not topic.strip()):
        with st.spinner("Running research → strategy → writing → editing pipeline..."):
            try:
                result = generate_post(
                    topic=topic,
                    vector_store=vs,
                    workspace_id=workspace_id,
                    competitor_name=None if competitor_choice == "None" else competitor_choice,
                )
                st.session_state.last_generated = result
            except Exception as e:
                st.error(f"Generation failed: {e}")

    if "last_generated" in st.session_state:
        result = st.session_state.last_generated
        st.subheader("Draft post")
        edited_post = st.text_area("Edit before saving:", value=result["post"], height=220)
        st.caption(f"**Suggested hashtags:** {result['hashtags']}")
        st.caption(f"**Image suggestion:** {result['image_suggestion']}")
        if result.get("competitor_feedback"):
            with st.expander("🔍 Competitor benchmarking feedback"):
                st.write(result["competitor_feedback"])

        colA, colB, colC = st.columns(3)
        if colA.button("💾 Save as draft"):
            db.add_post(workspace_id, edited_post, topic=topic, status="draft")
            st.success("Saved as draft.")
        if colB.button("📤 Share to WhatsApp/Slack"):
            bundle = generate_share_bundle(edited_post)
            st.markdown(f"[Open WhatsApp share link]({bundle['whatsapp']})")
            if bundle["slack_webhook_configured"]:
                if post_to_slack(edited_post):
                    st.success("Posted to Slack channel.")
                else:
                    st.error("Slack post failed -- check SLACK_WEBHOOK_URL.")
            else:
                st.info("No SLACK_WEBHOOK_URL configured -- add one in Settings/.env to enable direct Slack posting.")
        if colC.button("✅ Publish now to LinkedIn"):
            ws = db.get_workspace(workspace_id)
            token = ws.get("linkedin_access_token") or os.getenv("LINKEDIN_ACCESS_TOKEN")
            if not token:
                st.error("No LinkedIn access token configured for this workspace. Add one in Settings.")
            else:
                try:
                    api = LinkedInAPI(access_token=token)
                    post_id = db.add_post(workspace_id, edited_post, topic=topic, status="draft")
                    urn = api.publish_post(edited_post)
                    db.mark_published(post_id, workspace_id, urn)
                    st.success(f"Published! LinkedIn post URN: {urn}")
                except LinkedInAPIError as e:
                    st.error(f"LinkedIn publish failed: {e}")

# ---------------------------------------------------------------------
# Page: Calendar (scheduled + draft posts)
# ---------------------------------------------------------------------
elif page == "📅 Calendar":
    st.header(f"Content Calendar — {selected_name}")
    tab_draft, tab_scheduled, tab_published = st.tabs(["Drafts", "Scheduled", "Published"])

    with tab_draft:
        for p in db.get_posts(workspace_id, status="draft"):
            with st.expander(p["topic"] or p["content"][:60]):
                st.write(p["content"])
                sched_date = st.date_input("Schedule for", key=f"sched_{p['id']}")
                if st.button("Schedule", key=f"schedbtn_{p['id']}"):
                    db.update_post(p["id"], workspace_id, status="scheduled",
                                    scheduled_date=sched_date.isoformat())
                    st.rerun()

    with tab_scheduled:
        for p in db.get_posts(workspace_id, status="scheduled"):
            st.write(f"📅 **{p['scheduled_date']}** — {p['content'][:120]}...")

    with tab_published:
        for p in db.get_posts(workspace_id, status="published"):
            st.write(f"✅ {p['content'][:120]}... — 👍 {p['likes']} 💬 {p['comments']}")

# ---------------------------------------------------------------------
# Page: Analytics
# ---------------------------------------------------------------------
elif page == "📊 Analytics":
    st.header(f"Analytics — {selected_name}")
    posts = db.get_posts(workspace_id, status="published")
    if not posts:
        st.info("No published posts yet.")
    else:
        import pandas as pd
        df = pd.DataFrame(posts)[["topic", "likes", "comments", "impressions", "created_at"]]
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("topic")[["likes", "comments"]])

# ---------------------------------------------------------------------
# Page: Competitors
# ---------------------------------------------------------------------
elif page == "🔍 Competitors":
    st.header(f"Competitors — {selected_name}")
    st.info(
        "LinkedIn's public API doesn't allow pulling posts from profiles/pages "
        "you don't manage. Paste competitor post text below manually -- the "
        "benchmarking agent uses this as its comparison set."
    )
    with st.form("add_competitor_post"):
        comp_name = st.text_input("Competitor name")
        comp_post_text = st.text_area("Paste their post text")
        col1, col2 = st.columns(2)
        comp_likes = col1.number_input("Likes (if known)", min_value=0, value=0)
        comp_comments = col2.number_input("Comments (if known)", min_value=0, value=0)
        if st.form_submit_button("Save competitor post") and comp_name and comp_post_text:
            register_manual_competitor_post(
                vs, db, workspace_id, comp_name, comp_post_text, comp_likes, comp_comments
            )
            st.success(f"Saved post for {comp_name}")

    st.subheader("Stored competitor posts")
    for c in db.get_competitors(workspace_id):
        posts = vs.get_top_competitor_posts(workspace_id, competitor_name=c["name"])
        with st.expander(f"{c['name']} ({len(posts)} posts stored)"):
            for p in posts:
                st.write(f"👍 {p['metadata'].get('likes', 0)} — {p['text'][:200]}...")

# ---------------------------------------------------------------------
# Page: Leads
# ---------------------------------------------------------------------
elif page == "🎯 Leads":
    st.header(f"Leads — {selected_name}")
    leads = db.get_leads(workspace_id)
    if not leads:
        st.info("No leads captured yet. Leads are detected from comment keywords "
                 "like 'DM me', 'pricing', 'demo', etc.")
    for lead in leads:
        st.markdown(
            f"**{lead['commenter_name'] or 'Unknown'}** matched on "
            f"`{lead['matched_keyword']}` — _{lead['comment_text']}_ "
            f"({lead['status']})"
        )

# ---------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------
elif page == "⚙️ Settings":
    st.header(f"Settings — {selected_name}")
    ws = db.get_workspace(workspace_id)

    st.subheader("LinkedIn connection")
    current_token_set = bool(ws.get("linkedin_access_token"))
    st.write("Token configured:" , "✅ Yes" if current_token_set else "❌ No (falls back to .env)")
    new_token = st.text_input("LinkedIn access token (per-workspace override)", type="password")
    if st.button("Save token"):
        if new_token.strip():
            try:
                api = LinkedInAPI(access_token=new_token.strip())
                person_urn = api.get_person_urn()
                db.set_workspace_linkedin_credentials(workspace_id, new_token.strip(), person_urn)
                st.success(f"Saved and verified. Person URN: {person_urn}")
            except LinkedInAPIError as e:
                st.error(f"Token didn't verify against LinkedIn's API: {e}")
