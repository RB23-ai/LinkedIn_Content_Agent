#  LinkedIn AI Strategist

A multi-tenant AI agent system that helps companies plan, write, and publish LinkedIn content — built with **CrewAI**, **Streamlit**, and **ChromaDB**.

Each company gets its own isolated workspace: content ideas, an AI writing pipeline (research → strategy → draft → edit → hashtags/image), a content calendar, competitor benchmarking, lead capture from comments, and one-click sharing to WhatsApp/Slack before publishing.

---

##  Features

- **Multi-company workspaces** with full data isolation (separate SQLite rows + separate ChromaDB collections per company)
- **AI agent pipeline** — Researcher → Strategist → Writer → Editor → Hashtag & Image suggestions, orchestrated with CrewAI
- **Competitor benchmarking** — paste in competitor posts, get AI feedback on how to beat them
- **Lead capture** — scans comments for buying-intent keywords ("DM me", "pricing", "demo") and logs them
- **Content calendar** — draft → scheduled → published, with a daily auto-publish job
- **Internal review loop** — share a draft to WhatsApp or a Slack channel before it goes live
- **Real LinkedIn publishing** — via LinkedIn's official REST API (not scraping)

---

##  Preview

The app is a Streamlit multi-page dashboard: a sidebar for switching between company workspaces and navigating pages (Ideas, Post Editor, Calendar, Analytics, Competitors, Leads, Settings), and a main panel for the page content. The Post Editor page shows a topic input, a "Generate with AI agents" button, the resulting draft with suggested hashtags/image, and Save / Share / Publish actions.

Run it locally with `streamlit run app.py` to see it live — see [Getting started](#-getting-started) below.

---

##  Project structure

```
linkedin-agent-system/
├── app.py                        # Streamlit UI — all pages
├── config/
│   └── agents.yaml               # Reference copy of agent personas
├── agents/                       # One file per CrewAI agent
│   ├── llm_factory.py            # Groq / Ollama LLM setup
│   ├── researcher.py
│   ├── strategist.py
│   ├── writer.py
│   ├── editor.py
│   ├── hashtag_agent.py
│   ├── image_agent.py             # Unsplash-backed image suggestions
│   ├── performance_analyst.py
│   ├── competitor_benchmarker.py
│   └── lead_detector.py
├── tasks/
│   └── definitions.py            # CrewAI task factory functions
├── utils/
│   ├── database.py               # Multi-tenant SQLite (workspace_id isolation)
│   ├── vector_store.py           # Per-workspace ChromaDB collections
│   ├── linkedin_publisher.py     # LinkedIn REST API wrapper (fetch/publish)
│   ├── crew_runner.py            # Composes the agent pipeline
│   ├── sharing_utils.py          # WhatsApp link + Slack webhook
│   ├── lead_capture.py           # Keyword + optional LLM lead detection
│   └── scheduler.py              # Daily auto-publish of scheduled posts
├── models/
│   └── schemas.py                # Pydantic data models
├── requirements.txt
├── .env.example
└── .gitignore
```

---

##  Getting your API keys

| Service | Purpose | Sign-up | Free tier |
|---|---|---|---|
| [Groq](https://groq.com) | LLM for agent reasoning | groq.com | Generous free tier |
| [Tavily](https://tavily.com) *(optional)* | Web search for the researcher agent | tavily.com | 1,000 searches/month |
| [LinkedIn Developers](https://www.linkedin.com/developers) | Publish posts, read your own profile | linkedin.com/developers | Free |
| [Unsplash](https://unsplash.com/developers) *(optional)* | Stock image suggestions | unsplash.com/developers | 50 requests/hour |

### LinkedIn app setup
1. Create an app at the LinkedIn Developer Portal.
2. Add the **"Share on LinkedIn"** product and **"Sign In with LinkedIn using OpenID Connect"**.
3. Under **Auth**, generate a 3-legged OAuth token with scopes: `openid profile email w_member_social`.
4. Put the token in `.env` as `LINKEDIN_ACCESS_TOKEN`.

>  **Heads up on competitor data**: LinkedIn's public API only lets an app read/publish for the *authenticated member's own profile* — it does **not** allow fetching posts from an arbitrary competitor's profile or page you don't administer. That requires LinkedIn's Marketing Developer Platform, a separately-approved partnership. This project handles competitor benchmarking by letting you **paste in** competitor post text/stats on the Competitors page instead — see the docstring in `utils/linkedin_publisher.py` for the full explanation.

---

##  Getting started

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # then fill in your keys

streamlit run app.py
```

The app opens at `http://localhost:8501`. Create a workspace from the sidebar, add a content idea, and hit **Generate with AI agents** on the Post Editor page.

---

##  Data isolation

- **SQLite**: every table (`ideas`, `posts`, `competitors`, `leads`) carries a `workspace_id` foreign key, and every read/write query in `utils/database.py` filters by it — including updates (`WHERE id = ? AND workspace_id = ?`), so a guessed or leaked row id from another company can never be edited cross-tenant.
- **ChromaDB**: each workspace gets its own **collection**, not just a metadata filter, so there's no code path that could accidentally leak another company's embeddings into a search result.

---

##  Scheduled publishing

`utils/scheduler.py` runs a daily background job (default 08:00 UTC) that publishes any post whose `scheduled_date` has arrived, for every workspace with a LinkedIn token configured.

⚠️ On Streamlit Community Cloud (and most serverless hosts), background processes and local files can be reset when the app goes idle or redeploys. For reliable production scheduling, run the publish job as a **separate process** — a cron job or small worker — that calls `utils.scheduler._publish_due_posts()` directly, rather than relying on it living inside the Streamlit app process.

---

##  Deployment

### Streamlit Community Cloud (free, fastest)
1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. **New app** → select your repo/branch → main file path `app.py`.
4. Under **Advanced settings → Secrets**, paste your `.env` values in TOML:
   ```toml
   GROQ_API_KEY = "..."
   LINKEDIN_ACCESS_TOKEN = "..."
   TAVILY_API_KEY = "..."
   ```
5. Deploy — you'll get a live `https://yourapp.streamlit.app` URL.

> Note: SQLite/Chroma data doesn't persist reliably across Streamlit Cloud restarts. For real customer data, use a small VPS with a persistent volume, or swap SQLite for a hosted Postgres (e.g. Supabase/Neon) before onboarding paying customers.

### Push to GitHub
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### Self-hosted
Any VPS with Docker; expose port `8501`. A ~$5/month DigitalOcean droplet is enough for a small number of workspaces.

---

##  Making it sellable

- **Billing** — gate workspace creation behind a Stripe subscription check.
- **Real authentication** — right now anyone with the app URL can switch between every workspace, which is fine for internal/team use but not for multi-customer SaaS. Add a `users` table mapping login → allowed `workspace_id`s.
- **Per-workspace LinkedIn tokens** — already supported via the Settings page, so each customer connects their own LinkedIn account.
- **Rate limiting / retries** — add backoff around `LinkedInAPI` calls and `crew_runner.generate_post`, since both LinkedIn and your LLM provider enforce rate limits.
- **Postgres migration** — swap out `utils/database.py`'s SQLite backend once you have concurrent multi-customer write traffic; method signatures are written to make that swap straightforward.

---

##  Tech stack

- [Streamlit](https://streamlit.io) — UI
- [CrewAI](https://www.crewai.com) — multi-agent orchestration
- [Groq](https://groq.com) — LLM inference (Llama 3.3 70B by default)
- [ChromaDB](https://www.trychroma.com) — per-workspace vector storage
- [APScheduler](https://apscheduler.readthedocs.io) — scheduled publishing
- SQLite — multi-tenant relational storage

---

##  License

Add your preferred license here (MIT is a common default for a project like this) before making the repo public.
