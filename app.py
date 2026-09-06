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
from utils.linkedin_publisher import (
    LinkedInAPI, LinkedInAPIError, register_manual_competitor_post, build_organization_urn,
)
from utils.sharing_utils import generate_share_bundle, post_to_slack
from utils.crew_runner import generate_post
from utils.scheduler import start_scheduler
from utils.theme import inject_custom_css, render_header, status_pill

load_dotenv()

st.set_page_config(page_title="LinkedIn AI Strategist", page_icon="🚀", layout="wide")
inject_custom_css()

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

@st.cache_resource
def get_scheduler():
    # st.cache_resource runs this ONCE per Streamlit server process and
    # shares the result across every session/rerun -- unlike
    # st.session_state, which is per-browser-tab and re-triggers this on
    # every new session, which is what caused SchedulerAlreadyRunningError.
    return start_scheduler(hour=8, minute=0)

get_scheduler()

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

render_header(selected_name)

# ---------------------------------------------------------------------
# Page: Ideas
# ---------------------------------------------------------------------
if page == "💡 Ideas":
    st.subheader("Content ideas")

    with st.form("new_idea_form"):
        title = st.text_input("Idea title")
        desc = st.text_area("Description / angle")
        score = st.slider("Estimated engagement potential", 1, 10, 5)
        submitted = st.form_submit_button("Add idea", type="primary")
        if submitted and title.strip():
            db.add_idea(workspace_id, title.strip(), desc.strip(), score)
            st.rerun()

    ideas = db.get_ideas(workspace_id)
    if not ideas:
        st.info("No ideas yet -- add one above.")
    status_kind = {"pending": "warning", "approved": "success", "rejected": "danger"}
    for idea in ideas:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            pill = status_pill(idea["status"], status_kind.get(idea["status"], "muted"))
            col1.markdown(f"**{idea['title']}** {pill}  \n{idea['description']}", unsafe_allow_html=True)
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
    st.subheader("Generate a post")

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
            active_identity = ws.get("linkedin_active_identity", "person")
            author_urn = (
                ws.get("linkedin_org_urn") if active_identity == "organization"
                else ws.get("linkedin_person_urn")
            )
            if not token:
                st.error("No LinkedIn access token configured for this workspace. Add one in Settings.")
            elif active_identity == "organization" and not author_urn:
                st.error("No company page connected. Connect one in Settings first.")
            else:
                try:
                    api = LinkedInAPI(access_token=token)
                    post_id = db.add_post(workspace_id, edited_post, topic=topic, status="draft")
                    urn = api.publish_post(edited_post, author_urn=author_urn)
                    db.mark_published(post_id, workspace_id, urn)
                    identity_label = "company page" if active_identity == "organization" else "personal profile"
                    st.success(f"Published as {identity_label}! LinkedIn post URN: {urn}")
                except LinkedInAPIError as e:
                    st.error(f"LinkedIn publish failed: {e}")

# ---------------------------------------------------------------------
# Page: Calendar (scheduled + draft posts)
# ---------------------------------------------------------------------
elif page == "📅 Calendar":
    st.subheader("Content calendar")
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
    st.subheader("Analytics")
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
    st.subheader("Competitors")
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
    st.subheader("Leads")
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
    st.subheader("Settings")
    ws = db.get_workspace(workspace_id)

    st.subheader("LinkedIn connection")
    st.caption(
        "Connect the identity this workspace should publish as. You can connect "
        "both a personal profile and a company page, then choose which one is "
        "active when publishing."
    )

    tab_person, tab_org = st.tabs(["👤 Personal profile", "🏢 Company page"])

    # ---------------- Personal profile tab ----------------
    with tab_person:
        person_connected = bool(ws.get("linkedin_person_urn"))
        if person_connected:
            st.success(f"Connected as **{ws.get('linkedin_person_name') or 'LinkedIn member'}**")
            st.caption(f"URN: `{ws['linkedin_person_urn']}`")
        else:
            st.info("Not connected yet.")

        with st.form("connect_person_form"):
            new_token = st.text_input(
                "LinkedIn access token",
                type="password",
                help="Generated from your LinkedIn Developer app's OAuth 2.0 Tools page, "
                     "with scopes: openid profile email w_member_social.",
            )
            submitted = st.form_submit_button("Connect / verify")
            if submitted:
                if not new_token.strip():
                    st.warning("Paste a token first.")
                else:
                    try:
                        api = LinkedInAPI(access_token=new_token.strip())
                        person_urn = api.get_person_urn()
                        person_name = api.get_person_display_name()
                        db.set_workspace_linkedin_credentials(
                            workspace_id, new_token.strip(), person_urn, person_name
                        )
                        st.success(f"Connected as {person_name}.")
                        st.rerun()
                    except LinkedInAPIError as e:
                        st.error(f"Couldn't verify this token against LinkedIn's API: {e}")

    # ---------------- Company page tab ----------------
    with tab_org:
        org_connected = bool(ws.get("linkedin_org_urn"))
        if org_connected:
            st.success(f"Connected: **{ws.get('linkedin_org_name') or ws['linkedin_org_urn']}**")
            st.caption(f"URN: `{ws['linkedin_org_urn']}`")
            if st.button("Disconnect company page"):
                db.clear_workspace_linkedin_org(workspace_id)
                st.rerun()
        else:
            st.info("Not connected yet.")
            st.caption(
                "LinkedIn doesn't offer an API to list pages you admin on a standard "
                "app tier, so paste the page's numeric ID instead — find it in your "
                "page admin view URL: linkedin.com/company/**12345678**/admin"
            )

        with st.form("connect_org_form"):
            org_id_input = st.text_input("Company page ID or URN")
            org_display_name = st.text_input("Display name for this page (optional)")
            submitted_org = st.form_submit_button("Connect company page")
            if submitted_org:
                if not org_id_input.strip():
                    st.warning("Enter a page ID or URN first.")
                else:
                    try:
                        org_urn = build_organization_urn(org_id_input)
                        db.set_workspace_linkedin_org(
                            workspace_id, org_urn, org_display_name.strip()
                        )
                        st.success("Company page saved. Note: actually publishing to it "
                                   "also requires LinkedIn to have granted this app admin "
                                   "access to that specific page.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    # ---------------- Active identity switch ----------------
    st.subheader("Publish as")
    options = ["Personal profile"] if not org_connected else ["Personal profile", "Company page"]
    if not person_connected and not org_connected:
        st.caption("Connect an identity above before choosing what to publish as.")
    else:
        current = ws.get("linkedin_active_identity", "person")
        default_index = 1 if (current == "organization" and org_connected) else 0
        choice = st.radio("Posts from this workspace will publish as:", options,
                           index=default_index, horizontal=True)
        if st.button("Save publishing identity"):
            db.set_active_linkedin_identity(
                workspace_id, "organization" if choice == "Company page" else "person"
            )
            st.success(f"Will publish as: {choice}")
            st.rerun()